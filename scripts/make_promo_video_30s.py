"""إنتاج فيديو ترويجي 30 ثانية: مشاهد + زووم + فلاتر + صوت عراقي + مؤثرات."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import edge_tts
import imageio_ffmpeg

ASSETS = Path(r"C:\Users\acer\.cursor\projects\c-Users-acer-goldenshield-GoldenShield-AI\assets")
OUT_DIR = Path(r"C:\Users\acer\goldenshield\GoldenShield_AI\storage\promo_video")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = "ar-IQ-RanaNeural"

# ترتيب المشاهد مع مدة تقريبية (مجموع ~30ث)
SCENES: list[tuple[str, float, str]] = [
    ("loc_01_girl_talking.png", 3.5, "هلا بيكم… إذا تريدون شي يبيّض الوجه، تعالوا وياي."),
    ("loc_motion_talk1.png", 1.5, ""),
    ("loc_02_cake_right.png", 4.0, "عدنا كيك طازج… أشكال ونكهات تفرّح القلب."),
    ("loc_03_flowers_left.png", 4.0, "وورد يعبّر عن مشاعركم… أحلى من الكلام."),
    ("loc_04_perfume_down.png", 4.0, "وعطور تترك بصمة… ريحة ما تننسى."),
    ("loc_05_candles_right.png", 4.0, "وشموع بأشكال فنية… تضيف لمسة رومانسية."),
    ("loc_06_gifts_left.png", 4.0, "وحتى اللمسات الناعمة… بذوق وأناقة."),
    ("loc_07_finale.png", 5.0, "كلشي بمكان واحد… تواصلوا وياانا، وخلّوا الفرحة تبدأ من عدنا."),
]

FULL_SCRIPT = " ".join(t for _, __, t in SCENES if t.strip())


async def make_voice(path: Path) -> None:
    communicate = edge_tts.Communicate(FULL_SCRIPT, VOICE, rate="-5%", pitch="+2Hz")
    await communicate.save(str(path))


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd[:8]), "...")
    subprocess.run(cmd, check=True)


def make_whoosh(path: Path, seconds: float = 0.35) -> None:
    # مؤثر صوتي خفيف انتقال
    run(
        [
            FFMPEG,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=680:duration={seconds}",
            "-af",
            "volume=0.08,afade=t=in:st=0:d=0.05,afade=t=out:st=0.2:d=0.15",
            str(path),
        ]
    )


def make_soft_bed(path: Path, seconds: float = 30.0) -> None:
    # خلفية موسيقية بسيطة ناعمة (بدون حقوق — توليف محلي)
    run(
        [
            FFMPEG,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=220:duration={seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=277:duration={seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=330:duration={seconds}",
            "-filter_complex",
            "[0]volume=0.03[a];[1]volume=0.02[b];[2]volume=0.015[c];[a][b][c]amix=inputs=3:duration=longest,afade=t=in:d=1,afade=t=out:st=28:d=2",
            str(path),
        ]
    )


def scene_clip(img: Path, out: Path, dur: float, zoom_end: float) -> None:
    # Ken Burns + فلتر لوني سينمائي خفيف
    # zoompan needs frames: fps*dur
    fps = 30
    frames = max(int(fps * dur), 1)
    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=increase,"
        f"crop=1080:1920,"
        f"zoompan=z='min(1.0+0.0015*on\\,{zoom_end})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={fps},"
        f"eq=contrast=1.06:saturation=1.12:brightness=0.02,"
        f"unsharp=5:5:0.4:5:5:0.0,"
        f"fade=t=in:st=0:d=0.25,fade=t=out:st={max(dur-0.3,0.1)}:d=0.3"
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
            str(dur),
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(out),
        ]
    )


def main() -> int:
    voice = OUT_DIR / "voice_iq_rana.mp3"
    bed = OUT_DIR / "bed.wav"
    whoosh = OUT_DIR / "whoosh.wav"
    concat_list = OUT_DIR / "concat.txt"
    video_silent = OUT_DIR / "video_silent.mp4"
    final = OUT_DIR / "PROMO_30s_IRAQI.mp4"

    print("SCRIPT:", FULL_SCRIPT)
    asyncio.run(make_voice(voice))
    make_soft_bed(bed, 30)
    make_whoosh(whoosh)

    clips: list[Path] = []
    for i, (name, dur, _) in enumerate(SCENES):
        src = ASSETS / name
        if not src.exists():
            # fallback talk frames
            alt = ASSETS / "loc_01_girl_talking.png"
            if not alt.exists():
                raise SystemExit(f"missing {name}")
            src = alt
        clip = OUT_DIR / f"clip_{i:02d}.mp4"
        zoom = 1.08 if i % 2 == 0 else 1.12
        scene_clip(src, clip, dur, zoom)
        clips.append(clip)

    # concat
    concat_list.write_text(
        "".join(f"file '{c.as_posix()}'\n" for c in clips),
        encoding="utf-8",
    )
    run(
        [
            FFMPEG,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            str(video_silent),
        ]
    )

    # اخلط الصوت: صوت + خلفية + مؤثرات خفيفة
    # اضبط طول الفيديو 30 ثانية
    run(
        [
            FFMPEG,
            "-y",
            "-i",
            str(video_silent),
            "-i",
            str(voice),
            "-i",
            str(bed),
            "-filter_complex",
            "[1:a]volume=1.25,afade=t=in:d=0.2,afade=t=out:st=28:d=1.5[v];"
            "[2:a]volume=0.55[b];"
            "[v][b]amix=inputs=2:duration=longest:dropout_transition=2[aout]",
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-t",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
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
