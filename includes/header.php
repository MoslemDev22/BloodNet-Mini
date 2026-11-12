<?php require_once __DIR__.'/helpers.php'; ?>
<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= e($pageTitle ?? APP_NAME) ?> | BloodNet</title>
<link rel="stylesheet" href="assets/style.css">
</head><body>
<aside class="sidebar">
  <div class="brand"><span class="brand-icon">✚</span><div><b>BloodNet</b><small>شبکه هوشمند خون</small></div></div>
  <nav>
    <a href="index.php" class="<?= ($active??'')==='dashboard'?'active':'' ?>">▦ <span>داشبورد</span></a>
    <a href="requests.php" class="<?= ($active??'')==='requests'?'active':'' ?>">▤ <span>درخواست‌های بیمارستان</span></a>
    <a href="inventory.php" class="<?= ($active??'')==='inventory'?'active':'' ?>">▣ <span>موجودی مراکز</span></a>
    <a href="donors.php" class="<?= ($active??'')==='donors'?'active':'' ?>">♙ <span>دعوت اهداکنندگان</span></a>
  </nav>
  <div class="sidebar-note"><b>نسخه آموزشی</b><p>اطلاعات و قواعد این سامانه ساختگی هستند و برای تصمیم پزشکی یا انتقال خون واقعی کاربرد ندارند.</p></div>
</aside>
<main class="main">
<header class="topbar"><div><span class="muted">سامانه مدیریت زنجیره تأمین خون</span><h1><?= e($pageTitle ?? 'داشبورد') ?></h1></div><div class="user"><span class="avatar">م</span><div><b>مدیر سامانه</b><small>کاربر آزمایشی</small></div></div></header>
<div class="content">
