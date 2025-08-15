# 🎵 Deezer Music Downloader & Converter

This Python tool lets you **search for or paste Deezer links** to download tracks in **FLAC**, then automatically:

* Convert to **WAV** (16-bit, 44.1 kHz, stereo) and **MP3** (320 kbps)
* Generate a `about.txt` file with detailed audio metadata (via ffprobe)
* Pack everything neatly into a ZIP archive

It uses **deemix** for downloading and **ffmpeg**/**ffprobe** for processing — with a nice progress bar in the console.

---

## ✨ Features

* **Search** Deezer tracks or albums by keywords
* **Paste** any Deezer link (short or full) — shortlinks are auto-expanded
* **High-quality FLAC downloads** via `deemix`
* **Automatic conversion** to WAV & MP3
* **Detailed audio info** file generation
* **ZIP packaging** for easy sharing
* Colorful console output with progress bars

---

## 📦 Requirements

### Python packages

```bash
pip install deemix colorama tqdm
```

### Binaries

You need `ffmpeg.exe` and `ffprobe.exe` in a `bin` folder inside the project directory:

```
project/
├─ bin/
│  ├─ ffmpeg.exe
│  ├─ ffprobe.exe
├─ get.py
```

Download them from:

* [FFmpeg official builds](https://ffmpeg.org/download.html)

---

## 🚀 Usage

1. **Clone this repository** or download the script.
2. **Install dependencies**:

   ```bash
   pip install deemix colorama tqdm
   ```
3. **Place ffmpeg & ffprobe** into the `bin` folder.
4. **Run the script**:

   ```bash
   python script.py
   ```

---

## 💡 How It Works

1. Script asks for **Deezer link** or **search query**.
2. If a search query is entered:

   * Searches Deezer API (tracks & albums)
   * Lets you pick a result
3. Downloads **FLAC** via `deemix`
4. Converts FLAC → WAV + MP3
5. Creates **about.txt** with audio info
6. Packs all into a ZIP in `Complete/` folder

---

## 📂 Output Structure

For each track, you’ll get:

```
TrackName.zip
 ├─ TrackName.flac
 ├─ TrackName.wav
 ├─ TrackName.mp3
 ├─ TrackName_about.txt
```

---

## 🛠 Notes

* Works **offline** after initial installation
* If you skip installing `colorama`/`tqdm`, script will still work but without colors and progress bars
* **Legal reminder**: Make sure you have rights to download the music

---

## 📜 License

This project is provided for **educational purposes only**.
The author is **not responsible** for misuse.
