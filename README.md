# MacSweep 🧹

**100% offline macOS storage manager, cache cleaner & file organizer — in your terminal.**

Open-source alternative to CleanMyMac, Hazel & Gemini 2.

No cloud. No telemetry. No subscriptions. Just clean your Mac.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://python.org)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-☕-orange.svg)](https://buymeacoffee.com/shubhamranga)

---

## ⚡ Quick Start

```bash
git clone https://github.com/shubhamxranga/macsweep.git
cd macsweep
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

---

## Features

### `1` Storage Scanner
- Recursive directory analysis using `os.scandir` (fast on APFS)
- Top files by size, top folders, file type breakdown
- Real-time disk usage bar

### `2` Duplicate Finder
- **Two-phase SHA-256 hashing** — groups by file size → hashes first 64KB → full SHA-256 only on matches
- Auto-select rules: keep newest, keep oldest, or manual pick
- Safe delete to `~/.macsweep/trash/` (not permanent)

### `3` Smart File Organizer
- Rule-based sorting using `default_rules.yaml` (Images, Docs, Code, Archives, etc.)
- Preview planned moves before executing
- Customizable rules — edit `app/config/default_rules.yaml`

### `4` Cache & Junk Cleaner
- Targets developer caches: **Homebrew**, **npm**, **pip**, **Xcode DerivedData**
- Clears old logs and `.DS_Store` files
- Safety tiers with confirmation for large cleanups (≥1GB requires typing "yes")

### Global Controls
- `u` — Undo last move/delete
- `Esc` — Back to dashboard
- `r` — Refresh stats

---

## 🛡️ Safety First

- **System folder protection** — `/System`, `/usr`, `/bin`, `/Library` are hardblocked
- **Trash staging** — Deletions go to `~/.macsweep/trash/`, not permanent removal
- **Undo logging** — Every move and delete is logged to `~/.macsweep/history.json` for one-key rollback

---

## 📂 Project Structure

```
macsweep/
├── main.py                  
├── demo.py                  
├── requirements.txt         
├── app/
│   ├── macsweep_app.py      
│   ├── screens/             
│   ├── widgets/             
│   ├── core/                
│   └── config/              
├── tests/                   
├── LICENSE                  
└── .gitignore
```

---

##  Run Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/awesome`)
3. Commit your changes (`git commit -m 'Add awesome feature'`)
4. Push to the branch (`git push origin feature/awesome`)
5. Open a Pull Request

---

## ☕ Support

If MacSweep saved you from a $40/year subscription, consider buying me a coffee:

**[☕ Buy Me a Coffee](https://buymeacoffee.com/shubhamranga)**

---

## 📄 License

MIT © [Shubham Ranga](https://github.com/shubhamxranga)
X/Twitter: x.com/ShubhamRanga_
