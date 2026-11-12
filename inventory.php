<?php
require_once 'includes/helpers.php';$pageTitle='موجودی مراکز انتقال خون';$active='inventory';$pdo=db();
$rows=$pdo->query("SELECT i.*,c.name center_name FROM inventory i JOIN centers c ON c.center_id=i.center_id WHERE i.units>0 ORDER BY i.expires_at ASC")->fetchAll();
require 'includes/header.php'; ?>
<section class="panel"><div class="panel-head"><div><h3>موجودی قابل بررسی</h3><p>اقلام بر اساس نزدیک‌ترین تاریخ انقضا مرتب شده‌اند (FEFO).</p></div><span class="pill"><?= count($rows) ?> ردیف موجودی</span></div>
<div class="table-wrap"><table><thead><tr><th>مرکز</th><th>فرآورده</th><th>گروه خونی</th><th>واحد باقی‌مانده</th><th>تاریخ انقضا</th><th>وضعیت</th></tr></thead><tbody><?php foreach($rows as $r): $expired=strtotime($r['expires_at'])<=time(); ?><tr><td><?= e($r['center_name']) ?></td><td><?= e($r['product']) ?></td><td><b class="blood"><?= e($r['blood_group']) ?></b></td><td><?= (int)$r['units'] ?></td><td><?= e($r['expires_at']) ?></td><td><span class="status <?= $expired?'cancelled':'fulfilled' ?>"><?= $expired?'منقضی':'قابل بررسی' ?></span></td></tr><?php endforeach; ?></tbody></table></div></section>
<?php require 'includes/footer.php'; ?>
