fn maybe_name() -> Option<String> {
    return Some("Koschei")
}

fn safe_number() -> Result<Int, Error> {
    return Ok(42)
}

fn failed_number() -> Result<Int, Error> {
    return Err(Error("Sayı üretilemedi"))
}
