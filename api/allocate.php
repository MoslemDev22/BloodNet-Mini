<?php
require_once __DIR__.'/../includes/helpers.php';
if($_SERVER['REQUEST_METHOD']!=='POST')jsonResponse(['error'=>'روش نامعتبر'],405);
$id=(int)($_GET['id']??0);$pdo=db();
try{$pdo->beginTransaction();
$q=$pdo->prepare("SELECT * FROM requests WHERE id=? FOR UPDATE");$q->execute([$id]);$r=$q->fetch();
if(!$r){$pdo->rollBack();jsonResponse(['error'=>'درخواست پیدا نشد.'],404);}
if(in_array($r['status'],['cancelled','fulfilled'],true)){$pdo->rollBack();jsonResponse(['error'=>'این درخواست قابل تخصیص نیست.'],409);}
$remaining=(int)$r['units']-(int)$r['fulfilled_units'];
if($remaining<=0){$pdo->commit();jsonResponse(['message'=>'درخواست قبلاً تأمین شده است.']);}
$groups=compatibleDonorGroups($r['product'],$r['blood_group']);$marks=implode(',',array_fill(0,count($groups),'?'));
$sql="SELECT * FROM inventory WHERE product=? AND blood_group IN ($marks) AND units>0 AND expires_at>NOW() ORDER BY expires_at ASC FOR UPDATE";
$stmt=$pdo->prepare($sql);$stmt->execute(array_merge([$r['product']],$groups));$stocks=$stmt->fetchAll();$allocated=0;
foreach($stocks as $stock){if($remaining<=0)break;$take=min($remaining,(int)$stock['units']);
$pdo->prepare("UPDATE inventory SET units=units-? WHERE id=? AND units>=?")->execute([$take,$stock['id'],$take]);
$pdo->prepare("INSERT INTO allocations(request_id,inventory_id,center_id,blood_group,product,units) VALUES(?,?,?,?,?,?)")->execute([$id,$stock['id'],$stock['center_id'],$stock['blood_group'],$stock['product'],$take]);
$remaining-=$take;$allocated+=$take;
}
$pdo->prepare("UPDATE requests SET fulfilled_units=fulfilled_units+? WHERE id=?")->execute([$allocated,$id]);
refreshRequestStatus($pdo,$id);
if($allocated>0)addEvent($pdo,$id,'تخصیص موجودی',"$allocated واحد از موجودی سازگار مراکز تخصیص داده شد.");
if($remaining>0)addEvent($pdo,$id,'کسری موجودی',"پس از بررسی موجودی، $remaining واحد کسری باقی مانده است.");
$pdo->commit();
jsonResponse(['allocated'=>$allocated,'remaining'=>$remaining,'message'=>$allocated>0?'بررسی موجودی انجام شد.':'موجودی سازگار کافی یافت نشد.']);
}catch(Throwable $e){if($pdo->inTransaction())$pdo->rollBack();jsonResponse(['error'=>'عملیات تخصیص ناموفق بود.','detail'=>$e->getMessage()],500);}
