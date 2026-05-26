# QDII ETF Support Design

## Goal

Support exchange-traded QDII ETFs inside the existing `asset_type=etf` flow without mislabeling local admission limits as vendor data failures.

## Scope

This change supports A-share exchange-traded QDII ETF codes such as `159501`, `159509`, `159513`, `513000`, and `513310`.

It does not support QDII-LOF products such as `501225`, non-exchange-traded funds, bond funds, money market funds, or a full overseas constituent/news data pipeline. QDII-LOF products require a separate `fund_basic`-based admission path and different product semantics, so they stay out of this change.

## Architecture

QDII remains a subtype of the existing ETF mode. `admit_etf()` should classify Tushare `etf_type=QDII` products as supported QDII ETFs when the code shape is an exchange-traded ETF code. Product, flow, and event packages should run normally for QDII ETFs. Holdings may degrade because Tushare `fund_portfolio` is often empty for these products.

The research package formatter should expose QDII-specific context so downstream agents know the product is cross-border:

- `cross_border=true`
- `qdii_profile=true`
- `index_code` and `index_name`
- `currency_fx_risk`
- `nav_lag_risk`
- `holiday_mismatch_risk`
- `premium_discount_risk`

## Data Flow

For QDII ETFs:

1. First-pass code detection still accepts normal ETF prefixes such as `15` and `51`.
2. `admit_etf()` fetches `etf_basic`, classifies `QDII`, and returns `is_supported=True`.
3. Product package uses `etf_basic`, `fund_nav`, and `fund_daily` to compute discount/premium where dates align.
4. Flow package uses `etf_share_size` when available.
5. Exposure package tries portfolio/index weights but returns a clear degraded status if unavailable.

For QDII-LOF:

1. `501225` remains rejected because it is not recognized by the current ETF code-shape gate.
2. The failure reason should remain product/scope related, not described as an open API outage.

## Error Handling

Blocked should mean out of scope, not "Tushare failed". QDII ETF packages should not return `blocked` solely because `etf_type=QDII`.

Missing QDII holdings or index weights should be reported as partial/unavailable fields with explanatory warnings.

## Tests

Add tests that mock ETF vendor calls and verify:

- QDII ETF admission is supported and classified as `qdii`.
- QDII product package is not blocked and includes cross-border risk context.
- QDII flow package is not blocked when share-size data exists.
- QDII exposure package degrades without blocking when holdings are empty.
- `501225` remains unsupported by the exchange-traded ETF gate.
