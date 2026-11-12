<?php
require_once 'includes/helpers.php';$pageTitle='دعوت اهداکنندگان';$active='donors';$pdo=db();
$rows=$pdo->query("SELECT d.*,r.blood_group recipient_group,r.product,r.id request_no FROM donor_invitations d JOIN requests r ON r.id=d.request_id ORDER BY d.id DESC")->fetchAll();
require 'includes/header.php'; ?>
<div class="notice">این صفحه شبیه‌سازی دعوت است؛ هیچ پیامک یا تماس واقعی ارسال نمی‌شود. پذیرش دعوت به معنی اهدای انجام‌شده نیست.</div>
<section class="panel"><div class="panel-head"><div><h3>وضعیت دعوت‌ها</h3><p>پاسخ‌ها و رویدادهای ثبت‌شده برای دعوت‌های آزمایشی</p></div></div><div class="table-wrap"><table><thead><tr><th>شناسه درخواست</th><th>شناسه اهداکننده</th><th>پاسخ</th><th>نتیجه مراجعه</th><th>زمان ثبت</th></tr></thead><tbody><?php foreach($rows as $d): ?><tr><td>#<?= $d['request_id'] ?></td><td><?= e($d['donor_code']) ?></td><td><?= e($d['response']) ?></td><td><?= e($d['result']) ?></td><td><?= e($d['created_at']) ?></td></tr><?php endforeach; ?><?php if(!$rows): ?><tr><td colspan="5" class="empty">هنوز دعوتی ثبت نشده است. در این نسخه، تمرکز روی ثبت درخواست و تخصیص موجودی است.</td></tr><?php endif; ?></tbody></table></div></section>
<?php require 'includes/footer.php'; ?>
