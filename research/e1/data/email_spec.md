# E-mail generator

`dict_emails` in `research/e1/e1lib.py` builds the list. It does not call a network service.

1. Read `surnames_head1000.csv`. Keep names for which `name.isalpha()` is true, in file order, and take the first 1,000. The shipped file is already that head. Lowercase each name.
2. Local parts: the bare surname, weight 0.25, and `initial.surname` for each of the 26 ASCII lowercase initials, together weight 0.75. No digits. The only added separator is the period after the initial.
3. Domains and weights: `gmail.com` 0.45, `outlook.com` 0.20, `yahoo.com` 0.15, `hotmail.com` 0.10, `icloud.com` 0.10.
4. A string's weight is the surname's Census count, divided by the sum of counts over the 1,000 names, times the local-part weight, times the domain weight.

The full 50,000-name surname list used by the main sweep is not shipped. Its Census CSV SHA-256 is `6b4933178060b4e5ac8dd9a611ec15472d35eab98fe9027474bc5ccc5b7a8708`. Set `E1_CENSUS` to that file before a re-render. `make all` does not render.
