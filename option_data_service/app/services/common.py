from datetime import date
from sqlalchemy.orm import Session
from ..models import DataSource, OptionContract, Symbol


def get_or_create_data_source(db: Session, code: str, name: str | None = None) -> DataSource:
    source = db.query(DataSource).filter(DataSource.code == code).first()
    if source:
        return source
    source = DataSource(code=code, name=name or code.title())
    db.add(source)
    db.flush()
    return source


def get_or_create_symbol(db: Session, ticker: str) -> Symbol:
    symbol = db.query(Symbol).filter(Symbol.ticker == ticker).first()
    if symbol:
        return symbol
    symbol = Symbol(ticker=ticker)
    db.add(symbol)
    db.flush()
    return symbol


def get_or_create_option_contract(db: Session, underlying_symbol_id: int, expiration: date, strike: float, option_type: str) -> OptionContract:
    contract = db.query(OptionContract).filter(
        OptionContract.underlying_symbol_id == underlying_symbol_id,
        OptionContract.expiration == expiration,
        OptionContract.strike == strike,
        OptionContract.option_type == option_type,
    ).first()
    if contract:
        return contract
    contract = OptionContract(
        underlying_symbol_id=underlying_symbol_id,
        expiration=expiration,
        strike=strike,
        option_type=option_type,
    )
    db.add(contract)
    db.flush()
    return contract
