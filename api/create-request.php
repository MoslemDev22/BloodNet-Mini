<?php
require_once __DIR__.'/../includes/helpers.php';
if($_SERVER['REQUEST_METHOD']!=='POST') jsonResponse(['error'=>'روش درخواست نامعتبر است.'],405);
$data=json_decode(file_get_contents('php://input'),true) ?? [];
$hospital=trim($data['hospital_id']??'');$group=$data['blood_group']??'';$product=$data['product']??'';$units=(int)($data['units']??0);$urgency=$data['urgency']??'';
if(!$hospital || !in_array($group,['O+','A+','B+','AB+','O-','A-','B-','AB-'],true) || !in_array($product,['red_cells','platelets','plasma'],true) || $units<1 || $units>20 || !in_array($urgency,['critical','urgent','planned'],true))
 jsonResponse(['error'=>'اطلاعات واردشده معتبر نیست.'],422);
$pdo=db();$q=$pdo->prepare("SELECT hospital_id FROM hospitals WHERE hospital_id=?");$q->execute([$hospital]);if(!$q->fetch())jsonResponse(['error'=>'بیمارستان انتخاب‌شده در سامانه وجود ندارد.'],422);
$key=$_SERVER['HTTP_IDEMPOTENCY_KEY']??bin2hex(random_bytes(16));
$hash=hash('sha256',json_encode($data));
try{$pdo->beginTransaction();
$old=$pdo->prepare("SELECT id,payload_hash FROM requests WHERE idempotency_key=? FOR UPDATE");$old->execute([$key]);$found=$old->fetch();
if($found){$pdo->rollBack();if($found['payload_hash']!==$hash)jsonResponse(['error'=>'کلید تکرار با اطلاعات متفاوت استفاده شده است.'],422);jsonResponse(['request_id'=>(int)$found['id'],'replayed'=>true],200);}
$ins=$pdo->prepare("INSERT INTO requests(hospital_id,blood_group,product,units,urgency,note,status,idempotency_key,payload_hash) VALUES(?,?,?,?,?,?,'open',?,?)");
$ins->execute([$hospital,$group,$product,$units,$urgency,substr(trim($data['note']??''),0,500),$key,$hash]);$id=(int)$pdo->lastInsertId();
addEvent($pdo,$id,'ثبت درخواست','درخواست جدید توسط بیمارستان ثبت شد.');$pdo->commit();
jsonResponse(['request_id'=>$id,'message'=>'درخواست با موفقیت ثبت شد.'],201);
}catch(Throwable $e){if($pdo->inTransaction())$pdo->rollBack();jsonResponse(['error'=>'خطا در ثبت درخواست.','detail'=>$e->getMessage()],500);}
