<?php
require_once 'includes/helpers.php'; $pageTitle='ثبت درخواست جدید'; $active='requests'; $pdo=db();
$hospitals=$pdo->query("SELECT hospital_id,name FROM hospitals ORDER BY name")->fetchAll();
require 'includes/header.php'; ?>
<div class="form-layout"><section class="panel"><div class="panel-head"><div><h3>اطلاعات درخواست</h3><p>مشخصات نیاز بیمارستان را وارد کنید.</p></div></div>
<form id="requestForm" class="form-grid">
<label class="full">بیمارستان درخواست‌کننده<select name="hospital_id" required><option value="">انتخاب بیمارستان</option><?php foreach($hospitals as $h): ?><option value="<?= e($h['hospital_id']) ?>"><?= e($h['name']) ?> (<?= e($h['hospital_id']) ?>)</option><?php endforeach; ?></select></label>
<label>نوع فرآورده<select name="product" required><option value="red_cells">گلبول قرمز</option><option value="platelets">پلاکت</option><option value="plasma">پلاسما</option></select></label>
<label>گروه خونی گیرنده<select name="blood_group" required><?php foreach(['O+','A+','B+','AB+','O-','A-','B-','AB-'] as $g): ?><option><?= $g ?></option><?php endforeach; ?></select></label>
<label>تعداد واحد<input type="number" name="units" min="1" max="20" value="2" required></label>
<label>سطح فوریت<select name="urgency"><option value="critical">بحرانی</option><option value="urgent" selected>فوری</option><option value="planned">عادی</option></select></label>
<label class="full">توضیحات (اختیاری)<textarea name="note" maxlength="500" rows="3" placeholder="توضیحات تکمیلی درخواست..."></textarea></label>
<div class="full form-actions"><a class="btn btn-ghost" href="requests.php">انصراف</a><button class="btn btn-primary" type="submit">ثبت و بررسی موجودی</button></div>
<div id="formMessage" class="full"></div>
</form></section><aside class="hint-card"><div class="hint-icon">ⓘ</div><h3>قبل از ثبت</h3><p>پس از ثبت درخواست، موجودی سازگار مراکز بررسی می‌شود و تخصیص بر اساس نزدیک‌ترین تاریخ انقضا انجام می‌گیرد.</p><ul><li>حداکثر تعداد در هر درخواست: ۲۰ واحد</li><li>واحد منقضی‌شده قابل تخصیص نیست.</li><li>قواعد سازگاری صرفاً داده‌های ساختگی مسابقه‌اند.</li></ul></aside></div>
<?php require 'includes/footer.php'; ?>
