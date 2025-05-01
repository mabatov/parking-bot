### 🅿️ Parking Bot  

A **Telegram bot** for monitoring parking spots using an **IP camera**. The bot captures real-time images from an **RTSP stream** and sends them to a Telegram chat, helping users find available parking spots faster.  

---

## 🚀 Features  
✅ Capture real-time images from an **IP camera**  
✅ Send images to a **Telegram chat**  
✅ **Fast and lightweight** – works in a Docker container  
✅ **Secure access** – only authorized users can request images  

---

## 🏗️ Technologies Used  
- **Backend**: Python, `python-telegram-bot`, FFmpeg  
- **Database**: PostgreSQL  
- **Containerization**: Docker, Docker Compose  

---

## 🔧 Installation & Setup  

### 1️⃣ Clone the Repository  
```bash
git clone https://github.com/mabatov/parking-bot.git
cd parking-bot
```

### 2️⃣ Configure the Bot  
Create an `.env` file with the following variables:  
```ini
bot_token=your_telegram_bot_token
logging_bot_token=your_logging_telegram_bot_token
rtsp_url=rtsp://user:password@camera-ip:port/stream1
admin_telegram_id=telegram_id_of_admin

db_user=db_name
db_password=db_password
db_host=localhost
db_port=5432
db_name=parking_bot
```

### 3️⃣ Run with Docker  
```bash
docker-compose up -d
```

---

## 📸 How It Works  
1️⃣ User sends a command to the bot (e.g., `/photo`)  
2️⃣ The bot **validates access** (checks if the user is authorized)  
3️⃣ The bot **fetches an image** from the RTSP stream using `FFmpeg`  
4️⃣ The bot **sends the image** back to the Telegram chat  

---

## 🛠️ Future Improvements  
🔹 **Computer vision** – automatically detect free parking spots  
🔹 **Web interface** – monitor the parking lot from a browser  
🔹 **Notification system** – get alerts when a parking spot is available  

---

## 📜 License  
This project is licensed under the **MIT License** – feel free to use and modify it! 🚀  

---

## ✉️ Contact  
📬 Have questions or suggestions? Open an **issue** or reach out via [Telegram](https://t.me/nvmabatov)!
