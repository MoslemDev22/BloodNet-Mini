<?php
require_once 'includes/helpers.php';
$pageTitle='داشبورد مدیریتی'; $active='dashboard'; $pdo=db();
$stats=[
 'requests'=>(int)$pdo->query("SELECT COUNT(*) FROM requests")->fetchColumn(),
 'open'=>(int)$pdo->query("SELECT COUNT(*) FROM requests WHERE status IN ('open','partially_fulfilled')")->fetchColumn(),
 'units'=>(int)$pdo->query("SELECT COALESCE(SUM(units),0) FROM inventory WHERE units>0 AND expires_at>NOW()")->fetchColumn(),
 'fulfilled'=>(int)$pdo->query("SELECT COUNT(*) FROM requests WHERE status='fulfilled'")->fetchColumn()
];
$latest=$pdo->query("SELECT r.*,h.name hospital_name FROM requests r JOIN hospitals h ON h.hospital_id=r.hospital_id ORDER BY r.id DESC LIMIT 6")->fetchAll();
require 'includes/header.php';
?>
<div class="notice" style="margin-bottom:16px">نسخه PHP/MySQL این صفحه یک نمونه آموزشی مستقل است. برای نسخه اصلی متصل به API و سرویس‌های شبیه‌سازی مسابقه، <a href="web/index.html" style="font-weight:700;color:#245b91">پنل یکپارچه BloodNet را باز کنید ←</a></div>
<section class="welcome"><div><span class="eyebrow">نمای کلی شبکه</span><h2>سلام، به BloodNet خوش آمدید</h2><p>وضعیت درخواست‌ها، موجودی مراکز و روند تأمین را از یک نقطه مدیریت کنید.</p></div><a class="btn btn-light" href="request-create.php">＋ ثبت درخواست جدید</a></section>
<div class="stats">
 <article class="stat"><div class="stat-icon red">▤</div><div><small>کل درخواست‌ها</small><strong><?= number_format($stats['requests']) ?></strong><span>ثبت‌شده در سامانه</span></div></article>
 <article class="stat"><div class="stat-icon orange">◷</div><div><small>درخواست‌های در جریان</small><strong><?= number_format($stats['open']) ?></strong><span>نیازمند پیگیری</span></div></article>
 <article class="stat"><div class="stat-icon green">▣</div><div><small>واحد موجودی قابل استفاده</small><strong><?= number_format($stats['units']) ?></strong><span>در مراکز انتقال خون</span></div></article>
 <article class="stat"><div class="stat-icon blue">✓</div><div><small>تأمین کامل</small><strong><?= number_format($stats['fulfilled']) ?></strong><span>درخواست تکمیل‌شده</span></div></article>
</div>
<section class="panel"><div class="panel-head"><div><h3>آخرین درخواست‌ها</h3><p>مرور وضعیت درخواست‌های ثبت‌شده</p></div><a class="text-link" href="requests.php">مشاهده همه ←</a></div>
<div class="table-wrap"><table><thead><tr><th>شناسه</th><th>بیمارستان</th><th>فرآورده</th><th>گروه خونی</th><th>تعداد</th><th>فوریت</th><th>وضعیت</th></tr></thead><tbody>
<?php if(!$latest): ?><tr><td colspan="7" class="empty">هنوز درخواستی ثبت نشده است.</td></tr><?php endif; ?>
<?php foreach($latest as $r): ?><tr><td>#<?= (int)$r['id'] ?></td><td><?= e($r['hospital_name']) ?></td><td><?= e(productFa($r['product'])) ?></td><td><b class="blood"><?= e($r['blood_group']) ?></b></td><td><?= (int)$r['units'] ?></td><td><?= e(urgencyFa($r['urgency'])) ?></td><td><span class="status <?= e($r['status']) ?>"><?= e(statusFa($r['status'])) ?></span></td></tr><?php endforeach; ?>
</tbody></table></div></section>
<?php require 'includes/footer.php';
function productFa($v){return ['red_cells'=>'گلبول قرمز','platelets'=>'پلاکت','plasma'=>'پلاسما'][$v]??$v;}
function urgencyFa($v){return ['critical'=>'بحرانی','urgent'=>'فوری','planned'=>'عادی'][$v]??$v;}
function statusFa($v){return ['open'=>'در انتظار تأمین','partially_fulfilled'=>'تأمین ناقص','fulfilled'=>'تأمین کامل','cancelled'=>'لغوشده'][$v]??$v;}
?>
