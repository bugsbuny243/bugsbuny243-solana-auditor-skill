fn maybe_value(enabled: Bool) -> Option<Int> {
    if enabled {
        return Some(42)
    }
    return None
}

fn calculate(enabled: Bool) -> Result<Int, Error> {
    if enabled {
        return Ok(7)
    }
    return Err(Error("disabled"))
}

fn checked(enabled: Bool) -> Result<Int, Error> {
    let value = calculate(enabled) or return
    return Ok(value + 1)
}

fn checked_custom(enabled: Bool) -> Result<Int, Error> {
    let value = calculate(enabled) or return Error("custom")
    return Ok(value)
}

fn main() {
    maybe_value(true)
    maybe_value(false)
    checked(true)
    checked(false)
    checked_custom(false)
    println("Koschei native safe types: PASS")
}
