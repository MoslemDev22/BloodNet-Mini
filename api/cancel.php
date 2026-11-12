<?php
require_once __DIR__.'/../includes/helpers.php';
$id=(int)($_GET['id']??0);$pdo=db();
$q=$pdo->prepare("UPDATE requests SET status='cancelled' WHERE id=? AND status NOT IN ('fulfilled','cancelled')");$q->execute([$id]);
if(!$q->rowCount())jsonResponse(['error'=>'درخواست پیدا نشد یا قابل لغو نیست.'],404);
addEvent($pdo,$id,'لغو درخواست','درخواست توسط کاربر لغو شد.');jsonResponse(['message'=>'درخواست لغو شد.']);
