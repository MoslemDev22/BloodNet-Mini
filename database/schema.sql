CREATE DATABASE IF NOT EXISTS bloodnet CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bloodnet;
CREATE TABLE hospitals(hospital_id VARCHAR(10) PRIMARY KEY,name VARCHAR(150) NOT NULL);
CREATE TABLE centers(center_id VARCHAR(10) PRIMARY KEY,name VARCHAR(150) NOT NULL);
CREATE TABLE inventory(
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, center_id VARCHAR(10) NOT NULL,
 blood_group VARCHAR(4) NOT NULL, product ENUM('red_cells','platelets','plasma') NOT NULL,
 units INT UNSIGNED NOT NULL DEFAULT 0, expires_at DATETIME NOT NULL,
 INDEX idx_stock(product,blood_group,expires_at), CONSTRAINT fk_inv_center FOREIGN KEY(center_id) REFERENCES centers(center_id)
) ENGINE=InnoDB;
CREATE TABLE requests(
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,hospital_id VARCHAR(10) NOT NULL,
 blood_group VARCHAR(4) NOT NULL,product ENUM('red_cells','platelets','plasma') NOT NULL,
 units TINYINT UNSIGNED NOT NULL,fulfilled_units TINYINT UNSIGNED NOT NULL DEFAULT 0,
 urgency ENUM('critical','urgent','planned') NOT NULL,note VARCHAR(500) NULL,
 status ENUM('open','partially_fulfilled','fulfilled','cancelled','expired') NOT NULL DEFAULT 'open',
 idempotency_key VARCHAR(128) NOT NULL UNIQUE,payload_hash CHAR(64) NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_req_hospital FOREIGN KEY(hospital_id) REFERENCES hospitals(hospital_id)
) ENGINE=InnoDB;
CREATE TABLE allocations(
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,request_id BIGINT UNSIGNED NOT NULL,
 inventory_id BIGINT UNSIGNED NOT NULL,center_id VARCHAR(10) NOT NULL,
 blood_group VARCHAR(4) NOT NULL,product VARCHAR(20) NOT NULL,units INT UNSIGNED NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(request_id) REFERENCES requests(id),FOREIGN KEY(inventory_id) REFERENCES inventory(id),
 FOREIGN KEY(center_id) REFERENCES centers(center_id)
) ENGINE=InnoDB;
CREATE TABLE request_events(
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,request_id BIGINT UNSIGNED NOT NULL,
 event_type VARCHAR(80) NOT NULL,message VARCHAR(500) NOT NULL,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(request_id) REFERENCES requests(id)
) ENGINE=InnoDB;
CREATE TABLE donor_invitations(
 id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,request_id BIGINT UNSIGNED NOT NULL,
 donor_code VARCHAR(30) NOT NULL,response ENUM('pending','accepted','declined') DEFAULT 'pending',
 result ENUM('not_started','en_route','arrived','donated','no_show') DEFAULT 'not_started',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(request_id) REFERENCES requests(id)
) ENGINE=InnoDB;
INSERT INTO hospitals VALUES
('H01','بیمارستان مهر آذرگان'),('H02','بیمارستان بهار آذرگان'),('H03','بیمارستان نور آذرگان'),
('H04','بیمارستان سینا آذرگان'),('H05','بیمارستان شفا بهارستان'),('H06','بیمارستان کوثر بهارستان'),
('H07','بیمارستان رازی پارسیان'),('H08','بیمارستان امید پارسیان'),('H09','بیمارستان مهرگان تبرا'),
('H10','بیمارستان ایران تبرا'),('H11','بیمارستان حکمت سروستان'),('H12','بیمارستان پارس نیلاب'),
('H13','بیمارستان روستایی ۱'),('H14','بیمارستان روستایی ۲');
INSERT INTO centers VALUES
('MC1','مرکز انتقال خون آذرگان'),('MC2','مرکز انتقال خون بهارستان'),
('MC3','مرکز انتقال خون پارسیان'),('MC4','مرکز انتقال خون تبرا'),('MC5','مرکز انتقال خون سروستان');
INSERT INTO inventory(center_id,blood_group,product,units,expires_at) VALUES
('MC1','O+','red_cells',4,DATE_ADD(NOW(),INTERVAL 12 DAY)),
('MC1','A+','red_cells',3,DATE_ADD(NOW(),INTERVAL 8 DAY)),
('MC2','O-','red_cells',2,DATE_ADD(NOW(),INTERVAL 20 DAY)),
('MC3','B+','red_cells',3,DATE_ADD(NOW(),INTERVAL 15 DAY)),
('MC4','AB+','plasma',5,DATE_ADD(NOW(),INTERVAL 90 DAY)),
('MC5','A+','plasma',4,DATE_ADD(NOW(),INTERVAL 60 DAY)),
('MC2','A+','platelets',2,DATE_ADD(NOW(),INTERVAL 3 DAY)),
('MC3','O+','platelets',3,DATE_ADD(NOW(),INTERVAL 2 DAY));
