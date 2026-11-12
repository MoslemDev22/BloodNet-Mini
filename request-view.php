<?php
require_once 'includes/helpers.php'; $id=(int)($_GET['id']??0); $pdo=db();
$q=$pdo->prepare("SELECT r.*,h.name hospital_name FROM requests r JOIN hospitals h ON h.hospital_id=r.hospital_id WHERE r.id=?");$q->execute([$id]);$r=$q->fetch();
if(!$r){http_response_code(404);exit('درخواست پیدا نشد');}
$pageTitle='جزئیات درخواست #'.$id;$active='requests';
$ev=$pdo->prepare("SELECT * FROM request_events WHERE request_id=? ORDER BY id DESC");$ev->execute([$id]);$events=$ev->fetchAll();
$alloc=$pdo->prepare("SELECT a.*,c.name center_name FROM allocations a JOIN centers c ON c.center_id=a.center_id WHERE request_id=? ORDER BY a.id DESC");$alloc->execute([$id]);$allocs=$alloc->fetchAll();
require 'includes/header.php'; ?>
<div class="toolbar"><a class="btn btn-ghost" href="requests.php">← بازگشت</a><?php if($r['status']!=='fulfilled' && $r['status']!=='cancelled'): ?><button class="btn btn-primary" id="allocateBtn" data-id="<?= $id ?>">بررسی و تخصیص موجودی</button><?php endif; ?></div>
<div class="detail-grid"><section class="panel"><div class="panel-head"><div><h3>خلاصه درخواست</h3><p><?= e($r['hospital_name']) ?></p></div><span class="status <?= e($r['status']) ?>"><?= e($r['status']) ?></span></div>
<div class="detail-stats"><div><small>موردنیاز</small><b><?= $r['units'] ?> واحد</b></div><div><small>تأمین‌شده</small><b><?= $r['fulfilled_units'] ?> واحد</b></div><div><small>باقی‌مانده</small><b><?= max(0,$r['units']-$r['fulfilled_units']) ?> واحد</b></div></div>
<div class="progress"><span style="width:<?= min(100,($r['fulfilled_units']/$r['units'])*100) ?>%"></span></div>
<p class="detail-line">فرآورده: <b><?= e($r['product']) ?></b>　 |　 گروه خونی: <b><?= e($r['blood_group']) ?></b>　 |　 فوریت: <b><?= e($r['urgency']) ?></b></p>
<div id="actionMessage"></div></section>
<section class="panel"><div class="panel-head"><div><h3>تخصیص‌های انجام‌شده</h3><p>موجودی برداشت‌شده از مراکز</p></div></div><div class="table-wrap"><table><thead><tr><th>مرکز</th><th>گروه</th><th>تعداد</th><th>تاریخ تخصیص</th></tr></thead><tbody><?php foreach($allocs as $a): ?><tr><td><?= e($a['center_name']) ?></td><td><?= e($a['blood_group']) ?></td><td><?= $a['units'] ?></td><td><?= e($a['created_at']) ?></td></tr><?php endforeach; ?><?php if(!$allocs): ?><tr><td colspan="4" class="empty">هنوز تخصیصی ثبت نشده است.</td></tr><?php endif; ?></tbody></table></div></section>
<section class="panel full"><div class="panel-head"><div><h3>تاریخچه رویدادها</h3><p>ردیابی تغییرات درخواست</p></div></div><div class="timeline"><?php foreach($events as $event): ?><div class="timeline-item"><i></i><div><b><?= e($event['event_type']) ?></b><p><?= e($event['message']) ?></p><small><?= e($event['created_at']) ?></small></div></div><?php endforeach; ?></div></section></div>
<?php require 'includes/footer.php'; ?>
