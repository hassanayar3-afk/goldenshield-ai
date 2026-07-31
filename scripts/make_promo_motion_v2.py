"""نسخة محسّنة: إطارات حركة أكثر + انتقالات سلسة + جودة أعلى."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg

ASSETS = Path(r"C:\Users\acer\.cursor\projects\c-Users-acer-goldenshield-GoldenShield-AI\assets")
OUT = Path(r"C:\Users\acer\goldenshield\GoldenShield_AI\storage\promo_video")
OUT.mkdir(parents=True, exist_ok=True)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# سلسلة حركة أسرع (~30ث)
FRAMES = [
    ("anim_01.png", 2.2),
    ("anim_02.png", 2.0),
    ("loc_motion_talk1.png", 1.8),
    ("anim_03_cake.png", 3.8),
    ("anim_04_flowers.png", 3.8),
    ("anim_05_perfume.png", 3.8),
    ("anim_06_candles.png", 3.8),
    ("anim_07_gifts.png", 3.8),
    ("anim_08_finale.png", 5.0),
]

SCRIPT = (
    "هلا بيكم… إذا تريدون شي يبيّض الوجه، تعالوا وياي. "
    "عدنا كيك طازج… أشكال ونكهات تفرّح القلب. "
    "وورد يعبّر عن مشاعركم… أحلى من الكلام. "
    "وعطور تترك بصمة… ريحة ما تننسى. "
    "وشموع بأشكال فنية… تضيف لمسة رومانسية. "
    "وحتى اللمسات الناعمة… بذوق وأناقة. "
    "كلشي بمكان واحد… تواصلوا وياانا، وخلّوا الفرحة تبدأ من عدنا."
)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


async def voice(path: Path) -> None:
    await edge_tts.Communicate(SCRIPT, "ar-IQ-RanaNeural", rate="+0%", pitch="+3Hz").save(str(path))


def still_to_clip(img: Path, out: Path, dur: float, zoom: float) -> None:
    fps = 30
    n = max(int(fps * dur), 2)
    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,"
        f"zoompan=z='min(1.02+0.002*on\\,{zoom})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)-10*sin(on/20)':"
        f"d={n}:s=1080x1920:fps={fps},"
        f"eq=contrast=1.08:saturation=1.15:brightness=0.03,"
        f"unsharp=5:5:0.6:5:5:0.0,"
        f"hqdn3d=1.5:1.5:3:3"
    )
    run(
        [
            FFMPEG,
            "-y",
            "-loop",
            "1",
            "-i",
            str(img),
            "-vf",
            vf,
            "-t",
            f"{dur:.2f}",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out),
        ]
    )


def main() -> int:
    vpath = OUT / "voice2.mp3"
    asyncio.run(voice(vpath))

    clips: list[Path] = []
    for i, (name, dur) in enumerate(FRAMES):
        src = ASSETS / name
        if not src.exists():
            raise SystemExit(f"missing {src}")
        clip = OUT / f"mclip_{i:02d}.mp4"
        still_to_clip(src, clip, dur, 1.10 if i % 2 == 0 else 1.14)
        clips.append(clip)

    # xfade chain for smoother transitions
    # build filter: [0][1]xfade=...[v01]; [v01][2]xfade=...
    td = 0.35
    inputs: list[str] = []
    for c in clips:
        inputs += ["-i", str(c)]

    # compute offsets
    durations = [d for _, d in FRAMES]
    filter_parts: list[str] = []
    prev = "[0:v]"
    acc = durations[0]
    out_label = prev
    for i in range(1, len(clips)):
        offset = max(acc - td, 0.01)
        label = f"[v{i}]"
        filter_parts.append(
            f"{prev}[{i}:v]xfade=transition=fade:duration={td}:offset={offset:.3f}{label}"
        )
        prev = label
        out_label = label
        acc = acc + durations[i] - td

    filter_complex = ";".join(filter_parts) if filter_parts else None
    silent = OUT / "motion_silent.mp4"
    if filter_complex:
        cmd = [FFMPEG, "-y", *inputs, "-filter_complex", filter_complex, "-map", out_label, "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p", str(silent)]
    else:
        cmd = [FFMPEG, "-y", "-i", str(clips[0]), "-c", "copy", str(silent)]
    run(cmd)

    # optional optical flow polish (may be heavy); skip if fails
    smooth = OUT / "motion_smooth.mp4"
    try:
        run(
            [
                FFMPEG,
                "-y",
                "-i",
                str(silent),
                "-vf",
                "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
                "-t",
                "30",
                "-c:v",
                "libx264",
                "-crf",
                "18",
                str(smooth),
            ]
        )
        video = smooth
    except Exception:
        video = silent

    bed = OUT / "bed.wav"
    if not bed.exists():
        run(
            [
                FFMPEG,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=220:duration=30",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=277:duration=30",
                "-filter_complex",
                "[0]volume=0.025[a];[1]volume=0.018[b];[a][b]amix=inputs=2,afade=t=in:d=1,afade=t=out:st=28:d=2",
                str(bed),
            ]
        )

    final = OUT / "PROMO_30s_MOTION.mp4"
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(video),
            "-i",
            str(vpath),
            "-i",
            str(bed),
            "-filter_complex",
            "[1:a]volume=1.3,afade=t=in:d=0.15,afade=t=out:st=28:d=1.2[v];"
            "[2:a]volume=0.45[b];"
            "[v][b]amix=inputs=2:duration=longest[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-t",
            "30",
            "-c:v",
            "libx264",
            "-crf",
            "17",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(final),
        ]
    )
    print("DONE", final)
    print("SIZE_MB", round(final.stat().st_size / 1024 / 1024, 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
