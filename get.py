import os
import sys
import subprocess
import shutil
import json
import time
from urllib.parse import urlparse, quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from zipfile import ZipFile

# Красота в консоли
try:
    from colorama import init as colorama_init, Fore, Style
    from tqdm import tqdm
    colorama_init(autoreset=True)
except ImportError:
    # Фолбэк, если забыли поставить colorama/tqdm
    class Dummy:
        RESET_ALL = ''
    class F:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = ''
    class S:
        BRIGHT = NORMAL = ''
    Fore = F()
    Style = S()
    def tqdm(iterable=None, total=None, desc=None, colour=None, bar_format=None):
        if iterable is None:
            class DummyBar:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def update(self, *args, **kwargs): pass
            return DummyBar()
        return iterable

# ====== Утилиты HTTP (без внешних утилит) ======
def http_get(url: str, timeout: int = 15, headers: dict = None):
    req = Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            final_url = resp.geturl()
            return data, final_url
    except (HTTPError, URLError):
        return None, None

def http_get_json(url: str, timeout: int = 15):
    data, _ = http_get(url, timeout=timeout)
    if not data:
        return None
    try:
        return json.loads(data.decode("utf-8", errors="ignore"))
    except Exception:
        return None

# ====== Разворачивание коротких ссылок Deezer ======
def expand_deezer_shortlink(url: str) -> str:
    hosts = ("link.deezer.com", "dzr.page.link", "deezer.page.link")
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        netloc = ""
    if not any(h in netloc for h in hosts):
        return url
    _, final_url = http_get(url, timeout=20)
    if not final_url:
        return url
    return final_url

# ====== Пути ======
BIN_PATH = os.path.join(os.getcwd(), "bin")
TEMP_DIR = os.path.join(os.getcwd(), "temp")
RELEASE_DIR = os.path.join(os.getcwd(), "Complete")
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(RELEASE_DIR, exist_ok=True)

bin_ffmpeg = os.path.join(BIN_PATH, "ffmpeg.exe")
bin_ffprobe = os.path.join(BIN_PATH, "ffprobe.exe")

# ====== Тихий запуск процессов ======
def run_cmd(cmd, check=True, capture=False, silent=False):
    try:
        if silent or capture:
            result = subprocess.run(
                cmd, check=check, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        else:
            result = subprocess.run(cmd, check=check, text=True)
        return result
    except subprocess.CalledProcessError:
        print(Fore.RED + "❌ Ошибка при выполнении команды: " + (cmd[0] if cmd else ""))
        raise

def check_binaries():
    missing = []
    if not os.path.isfile(bin_ffmpeg):
        missing.append("ffmpeg.exe")
    if not os.path.isfile(bin_ffprobe):
        missing.append("ffprobe.exe")
    if missing:
        print(Fore.RED + f"❌ Не найдены бинарники: {', '.join(missing)}. Ожидаются в {BIN_PATH}")
        sys.exit(1)

# ====== Расширенная инфа о файле ======
def get_file_info(file_path):
    result = run_cmd([
        bin_ffprobe, "-v", "error",
        "-show_entries",
        "format=duration,size,bit_rate,format_name,format_long_name,format_tags=artist,title,album,date,track,genre:"
        "stream=index,codec_name,codec_long_name,codec_type,sample_rate,channels,bits_per_sample",
        "-of", "default=noprint_wrappers=1", file_path
    ], capture=True, check=True, silent=True)
    return result.stdout.strip()

# ====== Парсинг Deezer URL ======
def get_id_from_path(path_parts):
    if not path_parts:
        return (None, None)
    locales = {"en","us","ru","de","fr","es","it","pt","nl","pl","jp","uk"}
    if path_parts[0] in locales:
        path_parts = path_parts[1:]
        if not path_parts:
            return (None, None)
    kind = path_parts[0]
    if kind == "track" and len(path_parts) > 1 and path_parts[1].isdigit():
        return ("track", path_parts[1])
    if kind == "album" and len(path_parts) > 1 and path_parts[1].isdigit():
        return ("album", path_parts[1])
    return (None, None)

def get_deezer_id(input_url):
    expanded = expand_deezer_shortlink(input_url)
    parsed = urlparse(expanded)
    path_parts = parsed.path.strip("/").split("/")
    kind, did = get_id_from_path(path_parts)
    if kind and did:
        return f"{kind}:{did}", expanded
    raise ValueError("Неподдерживаемый или некорректный Deezer URL")

# ====== Поиск через Deezer API v1 (до 20 результатов) ======
def is_deezer_like_url(s: str) -> bool:
    s = s.lower()
    return any(x in s for x in ["deezer.com","link.deezer.com","dzr.page.link","deezer.page.link"])

def search_tracks(query: str, limit: int = 20):
    q = quote(query)
    url = f"https://api.deezer.com/search?q={q}"
    data = http_get_json(url)
    results = []
    if data and isinstance(data, dict) and "data" in data:
        for item in data["data"]:
            try:
                title = item.get("title", "")
                artist = item.get("artist", {}).get("name", "")
                link = item.get("link", "")
                if link and "deezer.com/track/" in link:
                    results.append({
                        "type": "track",
                        "artist": artist,
                        "title": title,
                        "url": link
                    })
                    if len(results) >= limit:
                        break
            except Exception:
                continue
    return results

def search_albums(query: str, limit: int = 20):
    q = quote(query)
    url = f"https://api.deezer.com/search/album?q={q}"
    data = http_get_json(url)
    results = []
    if data and isinstance(data, dict) and "data" in data:
        for item in data["data"]:
            try:
                title = item.get("title", "")
                artist = item.get("artist", {}).get("name", "")
                link = item.get("link", "")
                if link and "deezer.com/album/" in link:
                    results.append({
                        "type": "album",
                        "artist": artist,
                        "title": title,
                        "url": link
                    })
                    if len(results) >= limit:
                        break
            except Exception:
                continue
    return results

def parse_type_filter(q: str):
    s = q.strip()
    if s.lower().startswith("track:"):
        return "track", s[6:].strip()
    if s.lower().startswith("album:"):
        return "album", s[6:].strip()
    return None, s

def search_deezer(query: str, limit: int = 20):
    tp, q = parse_type_filter(query)
    if tp == "track":
        return search_tracks(q, limit)
    if tp == "album":
        return search_albums(q, limit)
    # По умолчанию — сначала треки, затем альбомы
    tracks = search_tracks(q, limit)
    remaining = max(0, limit - len(tracks))
    albums = search_albums(q, remaining) if remaining > 0 else []
    return (tracks + albums)[:limit]

def prompt_pick(results):
    if not results:
        print(Fore.YELLOW + "⚠️ Ничего не найдено.")
        return None
    print(Fore.CYAN + Style.BRIGHT + "\n🎯 Найденные варианты (до 20):")
    for i, r in enumerate(results, 1):
        print(Fore.WHITE + f"{i:>2}. " + Fore.MAGENTA + f"[{r['type']}]" + Fore.WHITE + f" {r['artist']} - {r['title']}")
    while True:
        raw = input(Fore.CYAN + "Выберите номер (Enter — отмена): ").strip()
        if raw == "":
            return None
        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(results):
                return results[n - 1]
        print(Fore.YELLOW + "Введите корректный номер из списка.")

# ====== Загрузка через deemix (тихо) ======
def download_deezer(id_tag, full_url):
    print(Fore.GREEN + "⬇️  Скачивание FLAC...")
    # Прогресс «ожидания» (визуальная анимация, так как deemix не отдаёт прогресс)
    with tqdm(total=100, desc="Загрузка", colour="green", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}%") as pbar:
        # Запускаем deemix тихо
        run_cmd([sys.executable, "-m", "deemix", full_url, "-p", TEMP_DIR, "--bitrate", "FLAC"], check=True, silent=True)
        # Быстрая анимация заполнения
        for _ in range(10):
            time.sleep(0.05)
            pbar.update(10)

# ====== Конвертация и упаковка ======
def fake_progress(desc: str, seconds: float = 1.0, colour: str = "cyan"):
    steps = 20
    delay = max(0.0, seconds) / steps
    with tqdm(total=steps, desc=desc, colour=colour, bar_format="{l_bar}{bar} {n_fmt}/{total_fmt}") as pbar:
        for _ in range(steps):
            time.sleep(delay)
            pbar.update(1)

def process_track(file_path):
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    wav_file = os.path.join(RELEASE_DIR, f"{base_name}.wav")
    mp3_file = os.path.join(RELEASE_DIR, f"{base_name}.mp3")
    flac_file = os.path.join(RELEASE_DIR, f"{base_name}.flac")
    about_file = os.path.join(RELEASE_DIR, f"{base_name}_about.txt")

    print(Fore.CYAN + f"\n🎵 Обработка: " + Fore.WHITE + f"{os.path.basename(file_path)}")
    shutil.copy2(file_path, flac_file)

    print(Fore.CYAN + "🎚 Конвертация в WAV (16-bit 44.1kHz stereo)...")
    run_cmd([bin_ffmpeg, "-y", "-i", file_path, "-ar", "44100", "-ac", "2", "-sample_fmt", "s16", wav_file], check=True, silent=True)
    fake_progress("WAV", seconds=0.8, colour="cyan")

    print(Fore.CYAN + "🎚 Конвертация в MP3 320k...")
    run_cmd([bin_ffmpeg, "-y", "-i", file_path, "-b:a", "320k", mp3_file], check=True, silent=True)
    fake_progress("MP3", seconds=0.8, colour="cyan")

    print(Fore.CYAN + "📝 Создание отчёта about.txt...")
    with open(about_file, "w", encoding="utf-8") as f:
        f.write("Информация о файлах:\n\n")
        f.write("WAV:\n" + get_file_info(wav_file) + "\n\n")
        f.write("FLAC:\n" + get_file_info(flac_file) + "\n\n")
        f.write("MP3:\n" + get_file_info(mp3_file) + "\n")
    fake_progress("Отчёт", seconds=0.4, colour="yellow")

    print(Fore.CYAN + "📦 Архивирование...")
    files_to_pack = [flac_file, wav_file, mp3_file, about_file]
    with ZipFile(os.path.join(RELEASE_DIR, f"{base_name}.zip"), 'w') as zipf:
        for ff in tqdm(files_to_pack, desc="ZIP", colour="magenta", bar_format="{l_bar}{bar} {n_fmt}/{total_fmt}"):
            zipf.write(ff, os.path.basename(ff))
            time.sleep(0.05)

    # Удаляем промежуточные
    for ff in files_to_pack:
        if os.path.exists(ff):
            os.remove(ff)

# ====== main ======
def banner():
    print(Fore.CYAN + Style.BRIGHT + "="*60)
    print(Fore.GREEN + Style.BRIGHT + "   MP3, FLAC, WAV Getter")
    print(Fore.CYAN + Style.BRIGHT + "="*60)

def main():
    banner()
    check_binaries()

    user_input = input(Fore.WHITE + "Введите Deezer ссылку ИЛИ текст для поиска: ").strip()

    if not is_deezer_like_url(user_input):
        print(Fore.YELLOW + f"🔍 Поиск: {user_input}")
        fake_progress("Поиск", seconds=0.6, colour="green")
        results = search_deezer(user_input, limit=20)
        pick = prompt_pick(results)
        if not pick:
            print(Fore.YELLOW + "⚠️ Действие отменено.")
            return
        deezer_url = pick["url"]
    else:
        deezer_url = user_input

    try:
        id_tag, full_url = get_deezer_id(deezer_url)
    except ValueError as e:
        print(Fore.RED + f"Ошибка: {e}")
        return

    download_deezer(id_tag, full_url)

    # Сбор всех FLAC
    flac_files = []
    for root, _, files in os.walk(TEMP_DIR):
        for f in files:
            if f.lower().endswith(".flac"):
                flac_files.append(os.path.join(root, f))

    if not flac_files:
        print(Fore.RED + "❌ Не удалось скачать FLAC")
        return

    print(Fore.GREEN + f"📁 Найдено FLAC файлов: {len(flac_files)}")
    for fp in flac_files:
        try:
            process_track(fp)
        except Exception as e:
            print(Fore.YELLOW + f"⚠️ Ошибка обработки {os.path.basename(fp)}: {e}")

    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    os.makedirs(TEMP_DIR, exist_ok=True)
    print(Fore.GREEN + Style.BRIGHT + f"\n✅ Готово! ZIP-файлы в папке {RELEASE_DIR}")

if __name__ == "__main__":
    main()
