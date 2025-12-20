# iOS Wallet Manager Pro (GUI Version) - Support iOS 18.2-26.1

A professional Python-based tool with a **Graphical User Interface (GUI)** to customize Apple Wallet passes/cards on iOS devices using the **Books Exploit**.

> ⚠️ **IMPORTANT NOTE:** > This modification is **non-persistent** on most devices — changes will revert after a reboot.  
> **Note:** Persistence may vary depending on the device model and iOS version; on some devices, the modification might not stay at all after a restart.
>
> **Use at your own risk.**

---

## 🌟 Project Credits

- **Developer:** ✨𝗬𝗮𝗻𝗴𝗝𝗶𝗶𝗶メ3105🍉 ([@duongduong0908](https://twitter.com/duongduong0908))
- **Wallet ID Logs Exploit:** paragon ([@paragonarsi](https://twitter.com/paragonarsi))
- **bl_sbx Exploit:** Duy Tran ([@khanhduytran0](https://twitter.com/khanhduytran0))

---

## ✅ Prerequisites

### Device Configuration
- Turn **OFF** Find My iPhone  
- Enable **Developer Mode**  
- Install **Apple Books** → download at least **one book**  
  *(Required to generate UUID for the exploit)*

### System Requirements
- macOS (Recommended) or Linux  
- Python **3.x**  
- Device connected via USB (Trusted & Unlocked)

---

## 🛠 Installation

Install required Python libraries:

```bash
pip3 install PyQt5 pymobiledevice3 click requests packaging
```

> Depending on your system, you may need:
> ```bash
> sudo pip3 install ...
> ```

---

## 🚀 Usage

1. Connect your iPhone via USB and unlock it.
2. Run the GUI tool (requires sudo for USB access):

```bash
python3 path/to/main.py
```

---

## 🖥️ On the Interface

### **Step 1 — Scan ID**
- Remove the card from Apple Wallet if already added  
- Click **SCAN CARD ID**  
- Add the card to your Wallet  
- Then set your card as the **Default card** 

### **Step 2 — Save**
Save the detected Card ID with a custom alias for later use.

### **Step 3 — Select Image**
Choose a custom **PNG** or **JPG** background image.

### **Step 4 — Execute**
Click **EXECUTE (INJECT)** to begin the modification process.

---

## 🔄 During Execution

- Watch the **Progress Bar**  
- If you see **“Books UUID Missing”**:
  - Open the **Books** app → download any book  
  - The tool will automatically detect this and **resume**  
- Your device will automatically **respring** when finished  
