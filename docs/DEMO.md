# مسیر دموی BloodNet

## دمو محلی رابط وب

1. `pip install -r requirements.txt`
2. `start-local-demo.bat`
3. بازکردن `web/index.html`
4. ثبت درخواست در پنل بیمارستان و مشاهده شناسه.
5. بازکردن جزئیات و مرور event timeline و شمارنده‌ها.
6. مشاهده موجودی زنده از پنل مرکز.
7. مشاهده دعوت‌ها با شناسه donor و توکن `donor-demo-token`؛ پرتال فقط برای شبیه‌سازی تعاملی است.

## دمو Runner

1. همه سرویس‌های قبلی را ببندید.
2. `start-api.bat` را در یک پنجره اجرا کنید.
3. در پنجره دوم اجرا کنید:

```bash
python -m harness.runner --team http://127.0.0.1:8000 --scenario P-normal --seed 1000
```

4. نتیجه در `run_out/result.json` قرار می‌گیرد.
5. برای آزمون سوءاستفاده از `--scenario P-abuse` استفاده کنید؛ درخواست‌های H09 با الگوی غیرعادی باید pending_review شوند و H98 باید رد شود.

## توکن‌ها

- `hospital-token`
- `coordinator-token`
- `donor-demo-token` (فقط برای پرتال محلی)

## نکته

برای هر اجرای Runner سرویس API را restart کنید؛ ساعت شبیه‌سازی از صفر شروع می‌شود و state درخواست‌ها در حافظه است.
