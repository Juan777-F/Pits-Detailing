-- =====================================================================
-- LAVADERO APP · SCRIPT MAESTRO DE CONFIGURACIÓN (MySQL / Django)
-- Base de datos para MySQL Workbench
-- =====================================================================



-- Crear la base de datos para el lavadero
CREATE DATABASE IF NOT EXISTS lavadero_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

-- Seleccionar la base de datos para usarla
USE lavadero_db;
SET FOREIGN_KEY_CHECKS = 0;

-- Borrar tablas si ya existen (orden inverso por dependencias)
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS visit_services;
DROP TABLE IF EXISTS visits;
DROP TABLE IF EXISTS service_prices;
DROP TABLE IF EXISTS services;
DROP TABLE IF EXISTS vehicles;
DROP TABLE IF EXISTS owners;
DROP TABLE IF EXISTS profiles;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 1. profiles: Propietarios y Empleados autorizados
-- ---------------------------------------------------------------------
CREATE TABLE profiles (
    id VARCHAR(36) PRIMARY KEY, -- UID vinculado al sistema de usuarios
    nombre VARCHAR(150) NOT NULL,
    cedula_hash VARCHAR(255) NOT NULL,
    rol ENUM('admin', 'empleado') NOT NULL DEFAULT 'empleado',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 2. owners: Dueños de los vehículos (clientes del lavadero)
-- ---------------------------------------------------------------------
CREATE TABLE owners (
    id CHAR(36) PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    celular VARCHAR(10) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    CONSTRAINT ck_owners_celular CHECK (celular REGEXP '^3[0-9]{9}$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_owners_nombre ON owners(nombre(50));
CREATE INDEX idx_owners_updated_at ON owners(updated_at);

-- ---------------------------------------------------------------------
-- 3. vehicles: Un registro por PLACA (nunca se duplica al volver)
-- ---------------------------------------------------------------------
CREATE TABLE vehicles (
    id CHAR(36) PRIMARY KEY,
    placa VARCHAR(10) NOT NULL UNIQUE,
    tipo ENUM('automovil', 'camioneta') NOT NULL,
    marca VARCHAR(100),
    modelo VARCHAR(50),
    color VARCHAR(50),
    owner_id CHAR(36) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    CONSTRAINT fk_vehicles_owner FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE RESTRICT,
    CONSTRAINT ck_vehicles_placa CHECK (placa REGEXP '^[A-Z]{3}[0-9]{2}[0-9A-Z]$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_vehicles_owner ON vehicles(owner_id);

-- ---------------------------------------------------------------------
-- 4. services: Catálogo de 12 servicios fijos
-- ---------------------------------------------------------------------
CREATE TABLE services (
    id CHAR(36) PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    tipo_vehiculo ENUM('automovil', 'camioneta') NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    orden INT NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_tipo_nombre (tipo_vehiculo, nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 5. service_prices: Historial de tarifas
-- ---------------------------------------------------------------------
CREATE TABLE service_prices (
    id CHAR(36) PRIMARY KEY,
    service_id CHAR(36) NOT NULL,
    precio DECIMAL(12,0) NOT NULL CHECK (precio >= 0),
    vigente_desde TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by CHAR(36) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_prices_service FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
    CONSTRAINT fk_prices_creator FOREIGN KEY (created_by) REFERENCES profiles(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_prices_service ON service_prices(service_id, vigente_desde DESC);

-- ---------------------------------------------------------------------
-- 6. visits: Cada visita al lavadero
-- ---------------------------------------------------------------------
CREATE TABLE visits (
    id CHAR(36) PRIMARY KEY,
    vehicle_id CHAR(36) NOT NULL,
    owner_id CHAR(36) NOT NULL,
    fecha_ingreso DATE NOT NULL,
    hora_ingreso TIME NOT NULL,
    hora_entrega TIME NOT NULL,
    estado ENUM('pendiente', 'en_proceso', 'terminado', 'cancelado') NOT NULL DEFAULT 'pendiente',
    observaciones TEXT,
    total DECIMAL(12,0) NOT NULL DEFAULT 0 CHECK (total >= 0),
    created_by CHAR(36) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    CONSTRAINT fk_visits_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE RESTRICT,
    CONSTRAINT fk_visits_owner FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE RESTRICT,
    CONSTRAINT fk_visits_creator FOREIGN KEY (created_by) REFERENCES profiles(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_visits_fecha ON visits(fecha_ingreso);
CREATE INDEX idx_visits_vehicle ON visits(vehicle_id);
CREATE INDEX idx_visits_estado ON visits(estado);

-- ---------------------------------------------------------------------
-- 7. visit_services: Servicios de cada visita con precio congelado
-- ---------------------------------------------------------------------
CREATE TABLE visit_services (
    id CHAR(36) PRIMARY KEY,
    visit_id CHAR(36) NOT NULL,
    service_id CHAR(36) NOT NULL,
    precio_aplicado DECIMAL(12,0) NOT NULL CHECK (precio_aplicado >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    CONSTRAINT fk_vs_visit FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE,
    CONSTRAINT fk_vs_service FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE RESTRICT,
    UNIQUE KEY uq_visit_service_activo (visit_id, service_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 8. payments: Pagos (+) y devoluciones (-) (Inmutable: Solo Inserción)
-- ---------------------------------------------------------------------
CREATE TABLE payments (
    id CHAR(36) PRIMARY KEY,
    visit_id CHAR(36) NOT NULL,
    tipo ENUM('pago', 'devolucion') NOT NULL DEFAULT 'pago',
    valor DECIMAL(12,0) NOT NULL,
    metodo ENUM('efectivo', 'transferencia') NOT NULL,
    pagado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    registrado_por CHAR(36) NULL,
    nota TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_payments_visit FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE RESTRICT,
    CONSTRAINT fk_payments_registrar FOREIGN KEY (registrado_por) REFERENCES profiles(id) ON DELETE SET NULL,
    CONSTRAINT ck_payments_signo CHECK (
        (tipo = 'pago' AND valor > 0) OR (tipo = 'devolucion' AND valor < 0)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_payments_visit ON payments(visit_id);

-- ---------------------------------------------------------------------
-- 9. audit_log: Auditoría general de operaciones
-- ---------------------------------------------------------------------
CREATE TABLE audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tabla VARCHAR(100) NOT NULL,
    registro_id CHAR(36) NULL,
    accion VARCHAR(20) NOT NULL, -- INSERT, UPDATE, DELETE
    datos_antes JSON NULL,
    datos_despues JSON NULL,
    usuario CHAR(36) NULL,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 10. INSERCIÓN DEL CATÁLOGO DE LOS 12 SERVICIOS
-- ---------------------------------------------------------------------
INSERT INTO services (id, codigo, tipo_vehiculo, nombre, orden) VALUES
(UUID(), 'auto_basico', 'automovil', 'Básico', 1),
(UUID(), 'auto_super', 'automovil', 'Súper', 2),
(UUID(), 'auto_motor', 'automovil', 'Lavado de motor', 3),
(UUID(), 'auto_polichado', 'automovil', 'Polichado', 4),
(UUID(), 'auto_cojin_tela', 'automovil', 'Cojinería en tela', 5),
(UUID(), 'auto_cojin_cuero', 'automovil', 'Cojinería en cuero', 6),
(UUID(), 'cam_basico', 'camioneta', 'Básico', 1),
(UUID(), 'cam_super', 'camioneta', 'Súper', 2),
(UUID(), 'cam_motor', 'camioneta', 'Lavado de motor', 3),
(UUID(), 'cam_polichado', 'camioneta', 'Polichado', 4),
(UUID(), 'cam_cojin_tela', 'camioneta', 'Cojinería en tela', 5),
(UUID(), 'cam_cojin_cuero', 'camioneta', 'Cojinería en cuero', 6)
ON DUPLICATE KEY UPDATE nombre=nombre;

-- ---------------------------------------------------------------------
-- 11. VISTAS DE NEGOCIO Y REPORTES
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_precio_actual AS
SELECT sp1.service_id, sp1.precio, sp1.vigente_desde
FROM service_prices sp1
INNER JOIN (
    SELECT service_id, MAX(vigente_desde) as max_vigente
    FROM service_prices
    GROUP BY service_id
) sp2 ON sp1.service_id = sp2.service_id AND sp1.vigente_desde = sp2.max_vigente;

CREATE OR REPLACE VIEW v_visit_payments AS
SELECT 
    v.id AS visit_id,
    v.estado AS estado_servicio,
    v.total,
    COALESCE(SUM(p.valor), 0) AS pagado_neto,
    CASE 
        WHEN v.estado = 'cancelado' THEN 0
        ELSE v.total - COALESCE(SUM(p.valor), 0) 
    END AS saldo,
    CASE
        WHEN v.estado = 'cancelado' THEN 'anulado'
        WHEN v.total > 0 AND COALESCE(SUM(p.valor), 0) >= v.total THEN 'pagado'
        WHEN COALESCE(SUM(p.valor), 0) > 0 THEN 'abono_parcial'
        ELSE 'pendiente_pago'
    END AS estado_pago
FROM visits v
LEFT JOIN payments p ON p.visit_id = v.id
GROUP BY v.id, v.estado, v.total;

CREATE OR REPLACE VIEW v_ingresos_dia AS
SELECT DATE(pagado_en) AS fecha, SUM(valor) AS ingresos_netos
FROM payments
GROUP BY DATE(pagado_en);