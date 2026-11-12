# معماری BloodNet

## اجزا

```text
web/ (RTL browser UI)
  |  HTTP + Bearer demo tokens
  v
service/bloodnet_api.py :8000
  |-- participant contract: /requests, /callbacks/*
  |-- optional UI endpoints: /meta, /inventory, /requests list/events, /donors/*
  |-- in-memory request/event/idempotency state + locks
  |-- participant_kit/compat.yaml, rules.yaml, donors/history CSV
  |
  |---- Gateway :9100  (messages + official simulation clock + callbacks)
  |---- Travel  :9200  (shortlist route-time lookup; static matrix fallback)
  |---- Inventory :9300 (live stock + atomic dispatch + FEFO)
```

## تصمیم‌های کلیدی

- یک سرویس Python ساده انتخاب شده تا Runner رسمی بدون تبدیل قرارداد یا وابستگی به MySQL بتواند آن را روی پورت 8000 صدا بزند.
- Gateway مرجع زمان شبیه‌سازی است. زمان سیستم میزبان فقط برای sleep/retry شبکه استفاده می‌شود و در تصمیم‌های دامنه‌ای نقشی ندارد.
- فایل‌های CSV/YAML کیت immutable هستند؛ داده‌های اولیه موجودی فقط snapshot هستند و موجودی لحظه‌ای از Inventory API خوانده می‌شود.
- ماتریس سازگاری در زمان startup از `compat.yaml` بارگذاری می‌شود. هر موجودی قبل از dispatch با آن بررسی می‌شود.
- ترتیب اقلام بر اساس `expires_sim_min` است. سرویس Inventory خودش موجودی را به‌صورت اتمیک کم می‌کند و dispatch ID را برای retry idempotent نگه می‌دارد.
- برای هر درخواست یک قفل سراسری state و flag batch dispatch وجود دارد. رقابت میان درخواست‌های مختلف در نهایت توسط Inventory API و عملیات اتمیک dispatch کنترل می‌شود.
- هر donor در هر درخواست یک state machine دارد. callbackها با `event_id` deduplicate می‌شوند و eventهای دیررس با `sim_time` قدیمی‌تر کنار گذاشته می‌شوند.
- قبول دعوت فقط `confirmed` را افزایش می‌دهد؛ `fulfilled` فقط در `donated` یا رسیدن محموله stock پس از ETA افزایش می‌یابد.
- برای جلوگیری از overfill، donorهای پذیرفته‌شده و stock در مسیر از نیاز باقیمانده کم می‌شوند؛ هر donor برای هر درخواست حداکثر یک واحد محسوب می‌شود.
- درخواست‌های مشکوک در `pending_review` نگه داشته می‌شوند. هیچ dispatch یا دعوتی تا تأیید هماهنگ‌کننده انجام نمی‌شود.
- برای انتخاب donor از فیلترهای safety، quiet hours، deferral، سازگاری و تاریخچه پاسخ استفاده می‌شود. Travel API برای shortlist محدود فراخوانی می‌شود تا quota مصرف نشود؛ ماتریس کیت fallback است.

## چرخه درخواست

1. اعتبارسنجی و احراز هویت.
2. بررسی `Idempotency-Key` و ایجاد request.
3. بررسی الگوی سوءاستفاده؛ در صورت نیاز `pending_review`.
4. خواندن موجودی زنده، انتخاب سازگار و FEFO و ارسال dispatchهای idempotent.
5. محاسبه کسری پس از stock-in-flight و دعوت موجی از اهداکنندگان واجد شرایط.
6. دریافت response/progress/gateway-status callbackها؛ dedupe و transition monotonic.
7. تکمیل شمارنده‌ها، توقف دعوت‌های اضافی، لغو یا انقضا.

## محدودیت state

هسته API برای اجرای محلی مسابقه state را در حافظه نگه می‌دارد. Runner نیز اجرای تازه را با restart سرویس توصیه می‌کند. برای production، جداول پایدار، transactionهای DB و transactional outbox لازم خواهد بود؛ این نسخه چنین ادعایی ندارد.
