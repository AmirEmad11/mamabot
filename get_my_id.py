from telethon import TelegramClient
from config import API_ID, API_HASH, PHONE

async def main():
    client = TelegramClient(f"session_user_{PHONE.replace('+','').replace(' ','')}", API_ID, API_HASH)
    await client.start(phone=PHONE)
    
    me = await client.get_me()
    print(f"\n{'='*50}")
    print(f"📱 رقم الهاتف: {me.phone}")
    print(f"🆔 معرف المستخدم (ID): {me.id}")
    print(f"👤 الاسم: {me.first_name or ''} {me.last_name or ''}")
    print(f"🔗 اليوزر: @{me.username if me.username else 'لا يوجد'}")
    print(f"{'='*50}\n")
    
    await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
