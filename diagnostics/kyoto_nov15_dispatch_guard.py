"""Nov15 observer trigger validation; zero network and no implicit authorization."""
from pathlib import Path

class ActivationRejected(ValueError):
    pass

def validate_activation(*, event_name, confirmation, gate_path):
    if event_name == "workflow_dispatch":
        if confirmation != "NOV15-OBSERVE-TWO-ORIGINALS":
            raise ActivationRejected("NOV15_DISPATCH_EXPLICIT_CONFIRMATION_REQUIRED_NO_HTTP")
    elif event_name == "push":
        gate = Path(gate_path)
        if (not gate.is_file() or gate.is_symlink() or
            gate.read_text(encoding="utf8").strip() != "NOV15-OBSERVE-TWO-ORIGINALS"):
            raise ActivationRejected("NOV15_PUSH_ACTIVATION_FILE_REQUIRED_NO_HTTP")
    else:
        raise ActivationRejected("NOV15_UNEXPECTED_EVENT_NO_HTTP")
    return {"authorization":"explicit_one_shot", "http_authorized":False}
