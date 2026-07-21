fn main() {
    let mut count = 3

    while count > 0 {
        println(count)
        count = count - 1
    }

    if count == 0 {
        println("Koschei control flow: PASS")
    } else {
        println("Koschei control flow: FAIL")
    }
}
