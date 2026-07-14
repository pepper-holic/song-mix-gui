"""Devices/audiomixer.xml → 믹서 모델 파싱.

주의: Studio One XML은 `x:` 접두사를 선언 없이 사용 → 파싱 전에 루트에
xmlns:x를 주입한다. 쓰기는 텍스트 수술로만 하므로(직렬화 안 함) 원형 훼손 없음.
"""
import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

X_NS = "urn:studio-one-x"
XID = f"{{{X_NS}}}id"

CHANNEL_TAGS = ("AudioInputChannel", "AudioOutputChannel", "AudioTrackChannel",
                "AudioGroupChannel", "AudioEffectChannel")

_UID_RE = re.compile(r"\{[0-9A-Fa-f-]{36}\}")


def parse_xml(text: str) -> ET.Element:
    """미선언 x: 접두사에 네임스페이스를 주입해 표준 파싱."""
    root_tag = re.search(r"<(\w+)[ >]", text).group(1)
    injected = text.replace(f"<{root_tag}", f'<{root_tag} xmlns:x="{X_NS}"', 1)
    return ET.fromstring(injected)


@dataclass(frozen=True)
class Insert:
    slot_name: str          # FX01 등 (표시 순서는 체인 인덱스와 별개)
    chain_index: int        # 실제 체인 순서 (XML 등장 순)
    uid: str
    class_id: str
    device_name: str
    plugin_name: str        # classInfo name
    sub_category: str
    preset_path: str | None


@dataclass(frozen=True)
class Send:
    destination_uid: str
    destination_name: str


@dataclass(frozen=True)
class Channel:
    tag: str                # AudioTrackChannel 등
    group: str              # ChannelGroup name (AudioTrack 등)
    name: str               # Channel01 등 (그룹 내 식별자)
    label: str              # 표시 이름 (Presets/Envelopes 폴더 키)
    uid: str
    speaker_type: str | None
    destination_uid: str | None
    destination_name: str | None
    inserts: tuple[Insert, ...] = ()
    sends: tuple[Send, ...] = ()

    @property
    def kind(self) -> str:
        return self.tag.removeprefix("Audio").removesuffix("Channel").lower()


@dataclass
class MixerModel:
    channels: list[Channel] = field(default_factory=list)

    def by_uid(self) -> dict[str, Channel]:
        return {c.uid: c for c in self.channels}

    def by_label(self, label: str) -> Channel | None:
        return next((c for c in self.channels if c.label == label), None)

    def group(self, group_name: str) -> list[Channel]:
        return [c for c in self.channels if c.group == group_name]

    def to_dict(self) -> dict:
        return {"channels": [
            {"tag": c.tag, "group": c.group, "name": c.name, "label": c.label,
             "uid": c.uid, "kind": c.kind, "speakerType": c.speaker_type,
             "destinationUid": c.destination_uid,
             "destinationName": c.destination_name,
             "inserts": [{"slot": i.slot_name, "order": i.chain_index,
                          "uid": i.uid, "classId": i.class_id,
                          "deviceName": i.device_name, "pluginName": i.plugin_name,
                          "subCategory": i.sub_category, "presetPath": i.preset_path}
                         for i in c.inserts],
             "sends": [{"destinationUid": s.destination_uid,
                        "destinationName": s.destination_name} for s in c.sends]}
            for c in self.channels]}


def _direct_uid(el: ET.Element) -> str | None:
    for child in el:
        if child.tag == "UID" and child.get(XID) == "uniqueID":
            return child.get("uid")
    return None


def _parse_inserts(channel_el: ET.Element) -> tuple[Insert, ...]:
    inserts: list[Insert] = []
    for attrs in channel_el:
        if attrs.tag != "Attributes" or attrs.get(XID) != "Inserts":
            continue
        chain_index = 0
        for slot in attrs:
            slot_name = slot.get("name")
            if slot.tag != "Attributes" or not slot_name or slot_name == "Combinator":
                continue
            uid = class_id = device_name = plugin_name = sub_category = ""
            preset_path = None
            for child in slot:
                xid = child.get(XID)
                if child.tag == "UID" and xid == "uniqueID":
                    uid = child.get("uid", "")
                elif child.tag == "UID" and xid == "deviceClassID":
                    class_id = child.get("uid", "")
                elif child.tag == "Attributes" and xid == "deviceData":
                    device_name = child.get("name", "")
                elif child.tag == "Attributes" and xid == "ghostData":
                    for g in child.iter():
                        if g.get(XID) == "classInfo":
                            plugin_name = g.get("name", "")
                            sub_category = g.get("subCategory", "")
                elif child.tag == "String" and xid == "presetPath":
                    preset_path = child.get("text")
            if not uid and not class_id:
                continue  # Presets 메타 등 비인서트 항목
            inserts.append(Insert(slot_name, chain_index, uid, class_id,
                                  device_name, plugin_name, sub_category, preset_path))
            chain_index += 1
    return tuple(inserts)


def _parse_sends(channel_el: ET.Element) -> tuple[Send, ...]:
    sends: list[Send] = []
    for attrs in channel_el:
        if attrs.tag != "Attributes" or attrs.get(XID) != "Sends":
            continue
        for conn in attrs.iter("Connection"):
            if conn.get(XID) == "destination":
                obj = conn.get("objectID", "")
                m = _UID_RE.search(obj)
                if m:
                    sends.append(Send(m.group(0), conn.get("friendlyName", "")))
    return tuple(sends)


def parse_mixer(xml_text: str) -> MixerModel:
    root = parse_xml(xml_text)
    model = MixerModel()
    for group_el in root.iter("ChannelGroup"):
        group_name = group_el.get("name", "")
        for ch in group_el:
            if ch.tag not in CHANNEL_TAGS:
                continue
            uid = _direct_uid(ch)
            speaker = None
            dest_uid = dest_name = None
            for child in ch:
                if child.tag == "SpeakerSetup":
                    speaker = child.get("type")
                elif (child.tag == "Connection"
                      and child.get(XID) == "destination"):
                    m = _UID_RE.search(child.get("objectID", ""))
                    dest_uid = m.group(0) if m else None
                    dest_name = child.get("friendlyName")
            model.channels.append(Channel(
                tag=ch.tag, group=group_name, name=ch.get("name", ""),
                label=ch.get("label", ""), uid=uid or "", speaker_type=speaker,
                destination_uid=dest_uid, destination_name=dest_name,
                inserts=_parse_inserts(ch), sends=_parse_sends(ch)))
    return model
