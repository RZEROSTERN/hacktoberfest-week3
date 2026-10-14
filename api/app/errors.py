from fastapi import HTTPException


class Cancelled(Exception):
    """Raised inside a background job when the user cancelled it."""


ERROR_MESSAGES = {
    "engine_missing": "The transcription engine is not available.",
    "model_missing": "The speech model has not been downloaded yet.",
    "decoder_missing": "The macOS audio converter is missing, so audio files cannot be read.",
    "decode_failed": "The audio file could not be read. Try exporting it again as mp3, m4a or wav.",
    "transcribe_failed": "Something went wrong while transcribing. You can try again.",
    "interrupted": "The app was closed while transcribing. You can try again.",
    "audio_missing": "The audio file is no longer available. Please upload it again.",
    "llm_model_not_set": "No language model is selected yet.",
    "llm_model_missing": "The selected language model is not installed.",
    "llm_unreachable": "The language model engine is not running.",
    "llm_timeout": "The language model took too long to answer. Try again.",
    "llm_failed": "The language model returned an error. Try again.",
    "invalid_model_output": "The model's answer could not be understood, even after a retry.",
    "draft_invalid": "The draft broke a rule (it contained prices), even after a retry.",
    "not_enough_information": "The call did not contain enough information to draft a proposal.",
    "profile_missing": "Set up your profile first.",
    "empty_transcript": "The transcript is empty, so there is nothing to draft from.",
    "generation_failed": "Something went wrong while drafting. You can try again.",
    "ollama_unreachable": "The local AI engine is not running.",
    "ollama_failed": "The local AI engine returned an error. Try again.",
    "model_not_found": "No model with that name exists in the Ollama library. Check name and tag.",
    "invalid_model_name": "That is not a valid model name. Use name:tag, for example gemma4:e4b.",
    "cloud_model": (
        "Cloud models send your calls to a server. "
        "PostCall only uses models that run on this computer."
    ),
    "network_error": (
        "The download stopped because the network connection was lost. "
        "Try again: it continues where it left off."
    ),
    "checksum_mismatch": "The downloaded file was damaged, so it was deleted. Try again.",
    "download_failed": "The download server did not send the expected file. Try again later.",
    "pull_failed": "The model could not be downloaded. Try again.",
    "not_enough_disk": "There is not enough free disk space for this download.",
    "model_not_installed": "That model is not on this computer.",
    "setup_failed": "Something went wrong during setup. Try again.",
    "setup_busy": "A download is already in progress.",
    "nothing_to_resume": "There is no interrupted download to resume.",
    "compat_needed": "This model has not been checked on this computer yet.",
    "model_in_use": "This is the model in use. Switch to another model first.",
    "compat_no_chat": (
        "This model could not be run for writing tasks. "
        "It may be built for something else, like search."
    ),
    "compat_invalid_output": (
        "This model did not return the structured notes the app needs, even after a retry."
    ),
    "compat_not_enough": (
        "This model ran, but it found nothing useful in a short test call. "
        "It is probably too small."
    ),
    "compat_timeout": (
        "This model took too long on a short test. It may be too big for this computer."
    ),
    "compat_model_missing": "The model disappeared before it could be tested. Try again.",
    # Refusals the screens can run into. The code is stable and the web app translates by it;
    # the text is English.
    "profile_not_set_up": "The profile has not been set up yet.",
    "call_not_found": "Call not found.",
    "transcribe_first": "Transcribe the call before drafting a proposal.",
    "draft_in_progress": "A draft is already being written for this call.",
    "no_draft": "There is no draft for this call yet.",
    "draft_not_running": "Only a draft in progress can be cancelled.",
    "draft_not_ready": "The draft is not ready yet.",
    "unsupported_file_type": "Unsupported file type. Use mp3, m4a, wav or mp4.",
    "file_empty": "The file is empty.",
    "transcript_not_ready": "The transcript is not ready yet.",
    "call_not_running": "Only a running transcription can be cancelled.",
    "cannot_retry": "Only a failed transcription with its audio still on disk can be retried.",
    "cancel_transcription_first": "Cancel the transcription before deleting it.",
    "cancel_draft_first": "Cancel the draft before deleting the call.",
    "pdf_unsupported_characters": (
        "The PDF export cannot draw some characters in this proposal (it supports Western European "
        "languages). Export it as Markdown instead."
    ),
    "edit_summary_prices": "The summary never includes prices.",
    "edit_prices_outside_investment": (
        "Prices belong in the investment section only, not in {where}."
    ),
    "edit_unknown_segments": (
        "An item in {where} cites segments that are not in the transcript: {segments}."
    ),
    "edit_unknown_section": "Unknown section: {section}",
}


class ApiError(HTTPException):
    """A refused request. `code` is stable and `params` fill in its message, so the web app can show
    it in the user's language; the English text (`detail`) stays for anything that does not know
    the code."""

    def __init__(
        self, status_code: int, code: str, message: str | None = None, **params: object
    ) -> None:
        super().__init__(status_code, message if message is not None else ERROR_MESSAGES[code])
        self.code = code
        self.params = params
