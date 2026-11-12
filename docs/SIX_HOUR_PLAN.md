# نقشه اجرای نسخه مسابقه در ۶ ساعت

این برنامه برای اولویت‌بندی توسعه در شرایط مسابقه است؛ معماری فعلی پروژه با همین ترتیب طراحی شده است.

| بازه | اولویت | خروجی |
|---|---|---|
| ۰:۰۰–۰:۳۰ | مرور OpenAPI، قواعد و داده‌ها | قرارداد API و state machine مشخص |
| ۰:۳۰–۱:۳۰ | هسته درخواست | احراز هویت، validation، idempotency، approve/amend/cancel |
| ۱:۳۰–۲:۳۰ | موجودی | اتصال Inventory، compat.yaml، FEFO، dispatch idempotent و concurrency |
| ۲:۳۰–۳:۳۰ | اهداکنندگان | eligibility، deferral، quiet hours، donor commitment و موج دعوت |
| ۳:۳۰–۴:۳۰ | callback و مقاومت خطا | event dedupe، out-of-order، Retry-After، توقف دعوت و audit trail |
| ۴:۳۰–۵:۳۰ | رابط کاربری | بیمارستان، مرکز خون، اهداکننده و نمایش وضعیت/خطا |
| ۵:۳۰–۶:۰۰ | تست و تحویل | contract tests، سناریوهای P-normal/P-amend/P-abuse، README و DECLARED |

## شواهد تست موجود

- آزمون سیاه‌جعبه رسمی `harness.contract_tests`.
- آزمون‌های توسعه‌ای `tests/extended_contract.py`.
- اجرای سناریوی P-abuse با معیارهای safety و abuse-leak.

امتیاز یک اجرای کوتاه تمرینی معادل نمره ارزیابی نهایی نیست؛ برای مقایسه، سناریوهای کامل را با تنظیمات پیش‌فرض Runner اجرا کنید.
