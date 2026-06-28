-- Taksit Analytics MCP - database schema
-- REAL data: UCI "Default of Credit Card Clients" (30,000 real clients, real
-- default label). https://archive.ics.uci.edu/dataset/350
-- Running this script DROPS and recreates the table.
--
-- Notes:
--   * Monetary columns are in New Taiwan Dollars (NT$), as in the source data.
--   * pay_* columns are the repayment status per month (Apr..Sep 2005):
--       -2 / -1 / 0 = paid duly / no consumption,  >= 1 = months of delay.
--   * defaulted = TRUE means the client defaulted on the payment next month.

DROP TABLE IF EXISTS credit_clients CASCADE;

CREATE TABLE credit_clients (
    client_id    integer PRIMARY KEY,
    credit_limit numeric(12, 2) NOT NULL,           -- LIMIT_BAL
    sex          text NOT NULL,                      -- decoded to TR
    education    text NOT NULL,                      -- decoded to TR
    marriage     text NOT NULL,                      -- decoded to TR
    age          integer NOT NULL CHECK (age > 0),

    -- Repayment status, most recent month first (Sep .. Apr 2005)
    pay_sep integer, pay_aug integer, pay_jul integer,
    pay_jun integer, pay_may integer, pay_apr integer,

    -- Bill statement amount per month (NT$)
    bill_sep numeric(12, 2), bill_aug numeric(12, 2), bill_jul numeric(12, 2),
    bill_jun numeric(12, 2), bill_may numeric(12, 2), bill_apr numeric(12, 2),

    -- Amount actually paid per month (NT$)
    pay_amt_sep numeric(12, 2), pay_amt_aug numeric(12, 2), pay_amt_jul numeric(12, 2),
    pay_amt_jun numeric(12, 2), pay_amt_may numeric(12, 2), pay_amt_apr numeric(12, 2),

    defaulted boolean NOT NULL                       -- target label
);

CREATE INDEX idx_clients_defaulted ON credit_clients (defaulted);
CREATE INDEX idx_clients_age ON credit_clients (age);
CREATE INDEX idx_clients_education ON credit_clients (education);
CREATE INDEX idx_clients_limit ON credit_clients (credit_limit);
CREATE INDEX idx_clients_pay_sep ON credit_clients (pay_sep);
