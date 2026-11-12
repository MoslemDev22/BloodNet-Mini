<?php
require_once 'includes/helpers.php'; $pageTitle='درخواست‌های بیمارستان'; $active='requests'; $pdo=db();
$rows=$pdo->query("SELECT r.*,h.name hospital_name FROM requests r JOIN hospitals h ON h.hospital_id=r.hospital_id ORDER BY r.id DESC")->fetchAll();
function pfa($v){return ['red_cells'=>'گلبول قرمز','platelets'=>'پلاکت','plasma'=>'پلاسما'][$v]??$v;}
function ufa($v){return ['critical'=>'بحرانی','urgent'=>'فوری','planned'=>'عادی'][$v]??$v;}
function sfa($v){return ['open'=>'در انتظار تأمین','partially_fulfilled'=>'تأمین ناقص','fulfilled'=>'تأمین کامل','cancelled'=>'لغوشده'][$v]??$v;}
require 'includes/header.php'; ?>
<div class="toolbar"><div><p class="muted">فهرست و وضعیت تمام درخواست‌های ثبت‌شده</p></div><a class="btn btn-primary" href="request-create.php">＋ ثبت درخواست</a></div>
<section class="panel"><div class="table-wrap"><table><thead><tr><th>شناسه</th><th>بیمارستان</th><th>فرآورده</th><th>گروه</th><th>درخواستی</th><th>تأمین‌شده</th><th>فوریت</th><th>وضعیت</th><th>جزئیات</th></tr></thead><tbody>
<?php foreach($rows as $r): ?><tr><td>#<?= $r['id'] ?></td><td><?= e($r['hospital_name']) ?></td><td><?= pfa($r['product']) ?></td><td><b class="blood"><?= e($r['blood_group']) ?></b></td><td><?= $r['units'] ?></td><td><?= $r['fulfilled_units'] ?></td><td><?= ufa($r['urgency']) ?></td><td><span class="status <?= e($r['status']) ?>"><?= sfa($r['status']) ?></span></td><td><a class="text-link" href="request-view.php?id=<?= $r['id'] ?>">مشاهده ←</a></td></tr><?php endforeach; ?>
<?php if(!$rows): ?><tr><td colspan="9" class="empty">درخواستی وجود ندارد.</td></tr><?php endif; ?>
</tbody></table></div></section>
<?php require 'includes/footer.php'; ?>
