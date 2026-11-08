import logging
import urllib.parse
from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream, Pause
from app.config import settings

logger = logging.getLogger("sales_agent.twilio")

class TwilioService:
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_phone = settings.TWILIO_PHONE_NUMBER
        
        self.client: Optional[Client] = None
        if self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio client initialized.")
            except Exception as e:
                logger.warning(f"Failed to initialize Twilio client: {e}")

    def generate_twiml(
        self,
        host: str,
        call_id: str,
        is_secure: bool = True,
        agent_id: Optional[str] = None,
        customer_id: Optional[str] = None
    ) -> str:
        """
        Generate TwiML response instructing Twilio to initiate bidirectional Media Stream.
        A brief pause is added before the stream so the WebSocket has time to open and the
        agent's TTS greeting can be synthesized before the customer expects to hear anything.
        """
        response = VoiceResponse()
        # Give the WebSocket and TTS pipeline ~1s to initialize before the customer notices silence
        response.pause(length=1)
        connect = Connect()
        clean_host = (
            host.replace("http://", "")
            .replace("https://", "")
            .replace("ws://", "")
            .replace("wss://", "")
            .strip("/")
        )
        protocol = "wss" if is_secure else "ws"
        # Twilio stream URL
        stream_url = f"{protocol}://{clean_host}/ws/twilio-media"
        
        stream = Stream(url=stream_url)
        # Pass custom parameters to stream start event
        stream.parameter(name="call_id", value=call_id)
        if agent_id:
            stream.parameter(name="agent_id", value=agent_id)
        if customer_id:
            stream.parameter(name="customer_id", value=customer_id)
        connect.append(stream)
        response.append(connect)
        return str(response)

    def initiate_call(
        self,
        to_phone: str,
        call_id: str,
        customer_id: str,
        agent_id: str = "",
        public_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate outbound phone call using Twilio REST API.
        Points Twilio to our /twilio/voice webhook.
        """
        if not self.client:
            raise ValueError("Twilio credentials not configured. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.")

        base_url = (public_url or settings.PUBLIC_BASE_URL).rstrip("/")
        if not base_url:
            raise ValueError(
                "PUBLIC_BASE_URL is required to receive Twilio webhooks. "
                "Please configure PUBLIC_BASE_URL (e.g. your ngrok url https://xxxx.ngrok-free.app)."
            )

        query_params = urllib.parse.urlencode({
            "call_id": call_id,
            "customer_id": customer_id,
            "agent_id": agent_id
        })
        twiml_webhook_url = f"{base_url}/twilio/voice?{query_params}"
        status_callback_url = f"{base_url}/twilio/status?call_id={call_id}"

        logger.info(f"Initiating Twilio call to {to_phone} from {self.from_phone} (webhook: {twiml_webhook_url})")

        try:
            call = self.client.calls.create(
                to=to_phone,
                from_=self.from_phone,
                url=twiml_webhook_url,
                status_callback=status_callback_url,
                status_callback_event=["initiated", "ringing", "answered", "completed"],
                record=False
            )
            logger.info(f"Twilio call created successfully! SID: {call.sid}")
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status,
                "to": to_phone
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Twilio call initiation failed: {error_msg}")
            return {
                "success": False,
                "call_sid": None,
                "error": error_msg,
                "status": "failed"
            }

twilio_service = TwilioService()

