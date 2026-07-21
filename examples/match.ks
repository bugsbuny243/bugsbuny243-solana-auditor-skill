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

fn main() {
    match maybe_value(true) {
        Some(value) => {
            println(value)
        }
        None => {
            println(0)
        }
    }

    match maybe_value(false) {
        Some(value) => {
            println(value)
        }
        None => {
            println(0)
        }
    }

    match calculate(true) {
        Ok(value) => {
            println(value)
        }
        Err(error) => {
            println(error)
        }
    }

    match calculate(false) {
        Ok(value) => {
            println(value)
        }
        Err(error) => {
            println(error)
        }
    }

    println("Koschei match: PASS")
}
