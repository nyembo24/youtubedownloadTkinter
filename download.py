import yt_dlp
from yt_dlp.utils import format_bytes


def format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def print_duration(info: dict) -> None:
    duration = info.get("duration")
    if duration is None:
        print("Durée : inconnue")
        return

    duration_int = int(duration)
    print("Durée (secondes) :", duration_int)
    print("Durée (lisible)  :", format_duration(duration_int))


def print_formats(info: dict) -> None:
    print("\nFormats disponibles :")
    formats = info.get("formats") or []
    if not formats:
        print("Aucun format listé.")
        return

    # Tri par qualité (résolution)
    formats_sorted = sorted(formats, 
                           key=lambda x: (x.get("height") or 0, x.get("filesize") or 0), 
                           reverse=True)

    for f in formats_sorted:
        fmt_id = f.get("format_id") or ""
        if fmt_id.startswith("sb"):
            continue

        filesize = f.get("filesize") or f.get("filesize_approx")
        ext = f.get("ext") or "?"
        fmt_id = f.get("format_id") or "?"
        
        # Récupérer plus d'informations
        height = f.get("height")
        width = f.get("width")
        resolution = f"{width}x{height}" if height and width else "?"
        
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")
        
        # Déterminer le type de format
        if vcodec != "none" and acodec != "none":
            type_str = "🎬 A+V"
        elif vcodec != "none":
            type_str = "🎥 Vidéo"
        elif acodec != "none":
            type_str = "🎵 Audio"
        else:
            type_str = "❓"
        
        # Formatage de la taille
        size_str = format_bytes(filesize) if filesize else "taille inconnue"
        
        # Afficher les informations
        print(f"- id={fmt_id:<5} | {type_str} | {ext:<4} | résolution={resolution:<10} | {size_str}")


def get_ydl_opts(quiet: bool = True) -> dict:
    return {
        # SUPPRIMEZ "format" pour voir TOUS les formats disponibles
        # "format": "bv*+ba/best",
        "merge_output_format": "mp4",
        # cookies navigateur
        "cookiesfrombrowser": ("firefox",),
        # forcer runtime JS
        "js_runtimes": {"node": {}},
        # clients youtube (élargi pour plus de formats)
        "extractor_args": {
            "youtube": {
                # ios/android ne supportent pas les cookies -> warnings
                "player_client": ["web", "tv", "web_creator"]
            }
        },
        # simuler navigateur avec User-Agent plus réaliste
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        # timeouts/retries réseau
        "socket_timeout": 60,
        "retries": 10,
        "fragment_retries": 10,
        "no_warnings": True,
        "noprogress": True,
        "quiet": quiet,
        "verbose": False,
    }


def extract_info(url: str, quiet: bool = True) -> dict:
    ydl_opts = get_ydl_opts(quiet=quiet)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def print_audio_formats(info: dict, limit: int = 10) -> None:
    print("\nFormats audio disponibles :")
    formats = info.get("formats") or []
    audio_formats = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none"]
    for f in audio_formats[:limit]:
        fmt_id = f.get("format_id") or "?"
        ext = f.get("ext") or "?"
        abr = f.get("abr") or "?"
        filesize = f.get("filesize") or f.get("filesize_approx")
        size_str = format_bytes(filesize) if filesize else "?"
        print(f"  - id={fmt_id:<5} | {ext:<4} | {abr}kbps | {size_str}")


def run_cli(url: str) -> None:
    info = extract_info(url, quiet=False)
    print("=" * 70)
    print("Titre :", info["title"])
    print_duration(info)
    print_formats(info)
    print("=" * 70)
    print_audio_formats(info)


if __name__ == "__main__":
    # url = "https://youtu.be/kUoO6C3BTeI?si=sfzKXDYxdXyhUdxp"
    url = input("Entrer url ici >>> ")
    run_cli(url)
