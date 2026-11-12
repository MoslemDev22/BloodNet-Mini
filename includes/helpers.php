<?php
require_once __DIR__ . '/../config.php';
function e($value): string { return htmlspecialchars((string)$value, ENT_QUOTES, 'UTF-8'); }
function jsonResponse(array $data, int $status=200): never {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit;
}
function compatibleDonorGroups(string $product, string $recipient): array {
    // قواعد ساختگی مسابقه؛ فقط برای شبیه‌سازی آموزشی
    $map = [
      'red_cells'=>[
        'O+'=>['O+','O-'],'A+'=>['O+','A+','O-','A-'],'B+'=>['O+','B+','O-','B-'],
        'AB+'=>['O+','A+','B+','AB+','O-','A-','B-','AB-'],'O-'=>['O-'],
        'A-'=>['O-','A-'],'B-'=>['O-','B-'],'AB-'=>['O-','A-','B-','AB-']],
      'platelets'=>[
        'O+'=>['O+','O-'],'A+'=>['A+','A-'],'B+'=>['B+','B-'],'AB+'=>['AB+','AB-'],
        'O-'=>['O+','O-'],'A-'=>['A+','A-'],'B-'=>['B+','B-'],'AB-'=>['AB+','AB-']],
      'plasma'=>[
        'O+'=>['O+','A+','B+','AB+','O-','A-','B-','AB-'],
        'A+'=>['A+','AB+','A-','AB-'],'B+'=>['B+','AB+','B-','AB-'],
        'AB+'=>['AB+','AB-'],'O-'=>['O+','A+','B+','AB+','O-','A-','B-','AB-'],
        'A-'=>['A+','AB+','A-','AB-'],'B-'=>['B+','AB+','B-','AB-'],'AB-'=>['AB+','AB-']]
    ];
    return $map[$product][$recipient] ?? [];
}
function refreshRequestStatus(PDO $pdo, int $id): void {
    $q=$pdo->prepare("SELECT units, fulfilled_units FROM requests WHERE id=?");
    $q->execute([$id]); $r=$q->fetch();
    if (!$r) return;
    $status = ((int)$r['fulfilled_units'] >= (int)$r['units']) ? 'fulfilled' :
        (((int)$r['fulfilled_units'] > 0) ? 'partially_fulfilled' : 'open');
    $pdo->prepare("UPDATE requests SET status=? WHERE id=? AND status NOT IN ('cancelled','expired')")->execute([$status,$id]);
}
function addEvent(PDO $pdo, int $requestId, string $type, string $message): void {
    $pdo->prepare("INSERT INTO request_events(request_id,event_type,message) VALUES(?,?,?)")
        ->execute([$requestId,$type,$message]);
}
