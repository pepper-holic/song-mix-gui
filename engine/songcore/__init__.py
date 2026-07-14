"""songcore — Studio One .song 파서/라이터/전송 엔진."""
from .container import SongContainer, SongLockedError, check_write_allowed
from .mixer_parser import MixerModel, parse_mixer
from .topology import RoutingGraph, build_graph

MIXER_ENTRY = "Devices/audiomixer.xml"
CONSOLE_ENTRY = "Devices/mixerconsole.xml"
NOTEPAD_ENTRY = "notepad.xml"


def load_model(container: SongContainer) -> MixerModel:
    return parse_mixer(container.read_text(MIXER_ENTRY))
