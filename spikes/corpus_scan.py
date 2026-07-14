"""US-011: 고유 프로젝트(비 History) 기준 플러그인 빈도 재집계 + 라벨 중복 스윕.

산출: .omc/verify/plugin-frequency-unique.md
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.songcore import MIXER_ENTRY, SongContainer, load_model

SONGS = Path(r"C:/Users/yhkze/Documents/Studio Pro/Songs")
OUT = Path(__file__).resolve().parents[1] / ".omc/verify/plugin-frequency-unique.md"


def main() -> int:
    all_songs = sorted(SONGS.rglob("*.song"))
    unique = [s for s in all_songs if "History" not in s.parts]
    copies = [s for s in all_songs if "History" in s.parts]

    freq_unique: Counter[str] = Counter()
    freq_all: Counter[str] = Counter()
    label_dups: dict[str, list[str]] = defaultdict(list)

    for song in all_songs:
        c = SongContainer.read(song)
        if not c.has(MIXER_ENTRY):
            continue
        model = load_model(c)
        names = [i.plugin_name for ch in model.channels for i in ch.inserts]
        freq_all.update(names)
        if song in unique:
            freq_unique.update(names)
            # 라벨 중복 스윕 (Presets/Envelopes 충돌 축) — 고유 프로젝트만
            labels = Counter(ch.label for ch in model.channels if ch.label)
            for label, n in labels.items():
                if n > 1:
                    label_dups[song.name].append(f"{label} ×{n}")

    lines = ["# 플러그인 사용 빈도 재집계 (고유 프로젝트 기준)", "",
             f"- 전체 .song: {len(all_songs)} (고유 {len(unique)} + History 사본 {len(copies)})", "",
             "| 플러그인 (classInfo name) | 고유 29곡 빈도 | 전체 116파일 빈도 |",
             "|---|---|---|"]
    for name, n in freq_unique.most_common():
        lines.append(f"| {name} | {n} | {freq_all[name]} |")
    only_in_copies = [n for n in freq_all if n not in freq_unique]
    if only_in_copies:
        lines += ["", f"- 사본에만 등장: {', '.join(only_in_copies)}"]

    lines += ["", "## 라벨 중복 스윕 (Open Question 2)"]
    if label_dups:
        for song_name, dups in sorted(label_dups.items()):
            lines.append(f"- **{song_name}**: {', '.join(dups)}")
        lines.append("")
        lines.append("→ 동일 라벨 채널이 실존: Presets/Channels·Envelopes 폴더가 라벨 키라서 "
                     "충돌 가능 — transfer는 라벨 충돌을 UID와 별개 축으로 검사해야 함 (계획 1.6 확정).")
    else:
        lines.append("- 고유 프로젝트 29곡 전체에서 한 song 내 동일 라벨 채널 없음.")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"unique songs: {len(unique)}, copies: {len(copies)}")
    print("top unique freq:", freq_unique.most_common(8))
    print("label dups:", dict(label_dups) or "none")
    print("written:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
