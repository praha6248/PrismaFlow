"""Product niches used to generate synthetic Deliver-phase flows.

Each niche lists a seed, a problem, a persona and the screens of its critical path. Each screen is
(name, feature title, feature description, primary action label). The last screens are where the
persona reaches value.
"""

from __future__ import annotations

NICHES = [
    {
        "lang": "pl", "seed": "nauka gry na gitarze", "problem": "Brak czasu na regularne ćwiczenia",
        "persona": ("Kasia", "studentka", "krótkie lekcje akordów"),
        "screens": [
            ("Powitanie", "Szybki start", "Pierwsza lekcja w minutę", "Zacznij"),
            ("Poziom", "Test poziomu", "Dopasowanie trudności do ucznia", "Wybierz poziom"),
            ("Lista utworów", "Biblioteka utworów", "Ulubione piosenki z akordami", "Otwórz utwór"),
            ("Lekcja", "Interaktywna lekcja", "Akordy z podpowiedziami na żywo", "Graj"),
            ("Postępy", "Śledzenie postępów", "Seria dni i opanowane akordy", "Zobacz postęp"),
        ],
    },
    {
        "lang": "pl", "seed": "planowanie posiłków dla rodzin", "problem": "Codzienne pytanie co ugotować",
        "persona": ("Marta", "mama dwójki dzieci", "tygodniowy jadłospis w 5 minut"),
        "screens": [
            ("Start", "Profil rodziny", "Liczba osób i alergie", "Dalej"),
            ("Preferencje", "Preferencje smakowe", "Dania lubiane przez dzieci", "Zapisz"),
            ("Jadłospis", "Plan tygodnia", "Gotowy plan na 7 dni", "Generuj plan"),
            ("Lista zakupów", "Lista zakupów", "Składniki pogrupowane działami", "Utwórz listę"),
        ],
    },
    {
        "lang": "pl", "seed": "aplikacja do medytacji dla zapracowanych", "problem": "Stres i brak chwili dla siebie",
        "persona": ("Tomasz", "kierownik projektu", "trzyminutowe przerwy na oddech"),
        "screens": [
            ("Powitanie", "Krótka ankieta", "Poziom stresu na start", "Rozpocznij"),
            ("Nastrój", "Dziennik nastroju", "Szybka ocena samopoczucia", "Oceń"),
            ("Wybór sesji", "Sesje 3 minuty", "Krótkie nagrania oddechowe", "Wybierz sesję"),
            ("Sesja", "Odtwarzacz sesji", "Prowadzony oddech z dźwiękiem", "Odtwórz"),
        ],
    },
    {
        "lang": "pl", "seed": "wynajem rowerów miejskich", "problem": "Trudno znaleźć wolny rower w pobliżu",
        "persona": ("Paweł", "dojeżdżający do pracy", "rower w 2 minuty od domu"),
        "screens": [
            ("Mapa", "Mapa stacji", "Wolne rowery w pobliżu", "Pokaż rowery"),
            ("Stacja", "Szczegóły stacji", "Liczba rowerów i odległość", "Wybierz rower"),
            ("Płatność", "Szybka płatność", "Płatność jednym dotknięciem", "Zapłać"),
            ("Wypożyczenie", "Odblokowanie roweru", "Kod QR do odblokowania", "Odblokuj"),
        ],
    },
    {
        "lang": "pl", "seed": "opieka nad roślinami doniczkowymi", "problem": "Rośliny usychają przez zapominanie o podlewaniu",
        "persona": ("Ola", "graficzka pracująca zdalnie", "przypomnienia o podlewaniu"),
        "screens": [
            ("Start", "Szybka rejestracja", "Konto bez hasła", "Zacznij"),
            ("Dodaj roślinę", "Rozpoznawanie roślin", "Zdjęcie zamiast wpisywania nazwy", "Zrób zdjęcie"),
            ("Harmonogram", "Harmonogram podlewania", "Terminy dopasowane do gatunku", "Ustaw harmonogram"),
            ("Moje rośliny", "Przypomnienia", "Powiadomienie w dniu podlewania", "Włącz przypomnienia"),
        ],
    },
    {
        "lang": "pl", "seed": "budżet domowy dla par", "problem": "Brak kontroli nad wspólnymi wydatkami",
        "persona": ("Ania", "księgowa", "wspólny podgląd wydatków"),
        "screens": [
            ("Powitanie", "Wspólne konto", "Zaproszenie partnera", "Utwórz konto"),
            ("Kategorie", "Kategorie wydatków", "Gotowe kategorie domowe", "Wybierz kategorie"),
            ("Dodaj wydatek", "Szybki wydatek", "Kwota i kategoria w 3 sekundy", "Dodaj"),
            ("Podsumowanie", "Miesięczne podsumowanie", "Wykres wydatków na osobę", "Pokaż raport"),
        ],
    },
    {
        "lang": "pl", "seed": "rezerwacja wizyt u fryzjera", "problem": "Dzwonienie w godzinach pracy salonu",
        "persona": ("Julia", "pielęgniarka na zmiany", "rezerwacja poza godzinami pracy"),
        "screens": [
            ("Start", "Wyszukiwarka salonów", "Salony w okolicy", "Szukaj"),
            ("Salon", "Profil salonu", "Cennik i opinie", "Wybierz usługę"),
            ("Termin", "Kalendarz terminów", "Wolne godziny na żywo", "Wybierz termin"),
            ("Potwierdzenie", "Potwierdzenie wizyty", "SMS z przypomnieniem", "Potwierdź"),
        ],
    },
    {
        "lang": "pl", "seed": "nauka słówek angielskich", "problem": "Szybkie zapominanie nowych słów",
        "persona": ("Michał", "licealista", "codzienna powtórka w autobusie"),
        "screens": [
            ("Powitanie", "Cel nauki", "Matura lub podróże", "Zacznij naukę"),
            ("Zestawy", "Zestawy tematyczne", "Słówka pogrupowane tematami", "Wybierz zestaw"),
            ("Fiszki", "Fiszki z powtórkami", "Powtórki w odstępach", "Odkryj"),
            ("Wynik", "Statystyki nauki", "Opanowane słowa i seria", "Zobacz wynik"),
        ],
    },
    {
        "lang": "pl", "seed": "zamawianie lunchu do biura", "problem": "Długie ustalanie wspólnego zamówienia",
        "persona": ("Bartek", "programista", "zamówienie dla zespołu w minutę"),
        "screens": [
            ("Restauracje", "Lista restauracji", "Dowóz do biura do 30 minut", "Wybierz"),
            ("Menu", "Menu z filtrami", "Dania wege i bez glutenu", "Dodaj danie"),
            ("Koszyk", "Wspólny koszyk", "Zamówienie całego zespołu", "Przejdź do koszyka"),
            ("Zamówienie", "Śledzenie dostawy", "Czas dowozu na żywo", "Zamów"),
        ],
    },
    {
        "lang": "pl", "seed": "trening siłowy w domu", "problem": "Brak planu treningowego bez sprzętu",
        "persona": ("Karolina", "mama na urlopie", "20 minut treningu w domu"),
        "screens": [
            ("Start", "Ankieta formy", "Poziom i cele treningowe", "Zacznij"),
            ("Plan", "Plan bez sprzętu", "Ćwiczenia z masą ciała", "Pokaż plan"),
            ("Trening", "Minutnik ćwiczeń", "Serie z odliczaniem", "Start treningu"),
            ("Podsumowanie", "Dziennik treningów", "Spalone kalorie i seria", "Zapisz trening"),
        ],
    },
    {
        "lang": "pl", "seed": "adopcja psów ze schroniska", "problem": "Trudność w znalezieniu psa pasującego do domu",
        "persona": ("Piotr", "emeryt z ogrodem", "spokojny pies do towarzystwa"),
        "screens": [
            ("Powitanie", "Profil domu", "Dom, ogród i dzieci", "Dalej"),
            ("Psy", "Dopasowanie psów", "Psy pasujące do stylu życia", "Przeglądaj psy"),
            ("Profil psa", "Karta psa", "Charakter i potrzeby psa", "Poznaj psa"),
            ("Spotkanie", "Umówienie spotkania", "Wizyta w schronisku", "Umów spotkanie"),
        ],
    },
    {
        "lang": "pl", "seed": "wspólne przejazdy na studia", "problem": "Drogie dojazdy do miasta akademickiego",
        "persona": ("Zuzia", "studentka z małego miasta", "tani przejazd w weekend"),
        "screens": [
            ("Szukaj", "Wyszukiwarka przejazdów", "Trasa i data przejazdu", "Szukaj przejazdu"),
            ("Wyniki", "Lista kierowców", "Cena i ocena kierowcy", "Wybierz przejazd"),
            ("Rezerwacja", "Rezerwacja miejsca", "Miejsce bez telefonu", "Zarezerwuj"),
            ("Bilet", "Potwierdzenie przejazdu", "Kontakt i miejsce zbiórki", "Pokaż bilet"),
        ],
    },
    {
        "lang": "pl", "seed": "kontrola cukrzycy", "problem": "Ręczne zapisywanie pomiarów glukozy",
        "persona": ("Halina", "nauczycielka z cukrzycą typu 2", "prosty dziennik pomiarów"),
        "screens": [
            ("Start", "Profil zdrowia", "Typ cukrzycy i leki", "Zacznij"),
            ("Pomiar", "Szybki pomiar", "Wpis glukozy jednym ruchem", "Dodaj pomiar"),
            ("Dziennik", "Dziennik pomiarów", "Historia z posiłkami", "Pokaż dziennik"),
            ("Raport", "Raport dla lekarza", "Wydruk trendów z miesiąca", "Wyślij raport"),
        ],
    },
    {
        "lang": "pl", "seed": "sprzedaż używanych ubrań dzieci", "problem": "Dzieci szybko wyrastają z ubrań",
        "persona": ("Ewa", "mama trojga dzieci", "sprzedaż paczki ubrań w 5 minut"),
        "screens": [
            ("Start", "Konto sprzedawcy", "Rejestracja przez telefon", "Sprzedaj"),
            ("Zdjęcia", "Zdjęcia ogłoszenia", "Kilka zdjęć naraz", "Dodaj zdjęcia"),
            ("Opis", "Podpowiedź ceny", "Cena na podstawie podobnych", "Ustaw cenę"),
            ("Ogłoszenie", "Publikacja ogłoszenia", "Ogłoszenie widoczne od razu", "Opublikuj"),
        ],
    },
    {
        "lang": "pl", "seed": "nauka programowania dla dzieci", "problem": "Dzieci nudzą się suchymi kursami",
        "persona": ("Adam", "tata dziewięciolatka", "nauka przez zabawę"),
        "screens": [
            ("Powitanie", "Profil dziecka", "Wiek i zainteresowania", "Zacznij"),
            ("Mapa przygód", "Ścieżka misji", "Kolejne misje z nagrodami", "Wybierz misję"),
            ("Misja", "Klocki kodu", "Programowanie przeciąganiem", "Uruchom"),
            ("Nagroda", "Odznaki", "Odznaka za ukończoną misję", "Odbierz odznakę"),
        ],
    },
    {
        "lang": "pl", "seed": "zgłaszanie usterek w bloku", "problem": "Zarządca nie odpowiada na zgłoszenia",
        "persona": ("Krzysztof", "mieszkaniec osiedla", "zgłoszenie usterki ze zdjęciem"),
        "screens": [
            ("Start", "Wybór budynku", "Adres i numer lokalu", "Dalej"),
            ("Zgłoszenie", "Formularz usterki", "Kategoria i zdjęcie", "Zgłoś usterkę"),
            ("Status", "Status zgłoszenia", "Etapy naprawy na żywo", "Sprawdź status"),
            ("Ocena", "Ocena naprawy", "Opinia po zakończeniu", "Oceń naprawę"),
        ],
    },
    {
        "lang": "pl", "seed": "planowanie podróży z dziećmi", "problem": "Szukanie atrakcji przyjaznych rodzinom",
        "persona": ("Natalia", "mama i blogerka", "plan dnia z dziećmi"),
        "screens": [
            ("Cel podróży", "Wybór miejsca", "Miasto i daty pobytu", "Wybierz miasto"),
            ("Atrakcje", "Atrakcje rodzinne", "Miejsca dla dzieci z opiniami", "Pokaż atrakcje"),
            ("Plan dnia", "Plan dnia", "Trasa z przerwami na drzemkę", "Ułóż plan"),
            ("Mapa trasy", "Nawigacja", "Trasa offline", "Prowadź"),
        ],
    },
    {
        "lang": "pl", "seed": "wymiana książek między sąsiadami", "problem": "Książki zalegają na półkach",
        "persona": ("Irena", "emerytowana bibliotekarka", "wymiana książek na osiedlu"),
        "screens": [
            ("Start", "Lokalizacja", "Osiedle i promień", "Zacznij"),
            ("Półka", "Moja półka", "Książki do wymiany", "Dodaj książkę"),
            ("Szukaj", "Książki w okolicy", "Lista książek sąsiadów", "Szukaj książki"),
            ("Wymiana", "Umówienie wymiany", "Miejsce i godzina", "Zaproponuj wymianę"),
        ],
    },
    {
        "lang": "pl", "seed": "pomoc w nauce matematyki", "problem": "Brak pomocy przy zadaniach domowych",
        "persona": ("Kuba", "uczeń siódmej klasy", "wyjaśnienie zadania krok po kroku"),
        "screens": [
            ("Start", "Wybór klasy", "Program nauczania", "Zacznij"),
            ("Skan", "Skan zadania", "Zdjęcie zadania z zeszytu", "Zeskanuj"),
            ("Rozwiązanie", "Rozwiązanie krok po kroku", "Kolejne kroki z wyjaśnieniem", "Pokaż krok"),
            ("Ćwiczenia", "Podobne zadania", "Trening na podobnych", "Ćwicz"),
        ],
    },
    {
        "lang": "pl", "seed": "kalendarz szczepień zwierząt", "problem": "Zapominanie o szczepieniach pupila",
        "persona": ("Agnieszka", "właścicielka dwóch kotów", "przypomnienia o wizytach"),
        "screens": [
            ("Powitanie", "Profil zwierzęcia", "Gatunek i data urodzenia", "Dodaj pupila"),
            ("Książeczka", "Cyfrowa książeczka", "Historia szczepień", "Uzupełnij"),
            ("Weterynarz", "Wybór weterynarza", "Gabinety w okolicy", "Wybierz gabinet"),
            ("Wizyta", "Rezerwacja wizyty", "Termin z przypomnieniem", "Zarezerwuj"),
        ],
    },
    {
        "lang": "pl", "seed": "wolontariat w okolicy", "problem": "Nie wiadomo gdzie pomóc w wolnym czasie",
        "persona": ("Igor", "student socjologii", "jednorazowe akcje w weekend"),
        "screens": [
            ("Start", "Zainteresowania", "Dziedziny pomocy", "Zacznij"),
            ("Akcje", "Lista akcji", "Akcje w najbliższy weekend", "Przeglądaj"),
            ("Akcja", "Szczegóły akcji", "Czas, miejsce i wymagania", "Zgłoś się"),
            ("Zgłoszenie", "Potwierdzenie udziału", "Kontakt do koordynatora", "Potwierdź udział"),
        ],
    },
    {
        "lang": "pl", "seed": "zakupy spożywcze dla seniorów", "problem": "Seniorom trudno nosić ciężkie zakupy",
        "persona": ("Stanisław", "emeryt", "zamówienie zakupów z dostawą"),
        "screens": [
            ("Start", "Duży tryb", "Większe litery i przyciski", "Zacznij"),
            ("Produkty", "Ulubione produkty", "Lista stałych zakupów", "Dodaj produkty"),
            ("Koszyk", "Koszyk", "Podsumowanie z ceną", "Przejdź dalej"),
            ("Dostawa", "Wybór dostawy", "Godzina dostawy do domu", "Zamów dostawę"),
        ],
    },
    {
        "lang": "pl", "seed": "nauka pływania dla dorosłych", "problem": "Wstyd przed nauką na basenie",
        "persona": ("Magda", "analityczka", "kameralne zajęcia dla początkujących"),
        "screens": [
            ("Powitanie", "Poziom pływania", "Ocena umiejętności", "Zacznij"),
            ("Baseny", "Baseny i godziny", "Spokojne godziny na basenie", "Wybierz basen"),
            ("Instruktor", "Wybór instruktora", "Instruktorzy dla dorosłych", "Wybierz instruktora"),
            ("Zapis", "Zapis na zajęcia", "Pakiet 4 lekcji", "Zapisz się"),
        ],
    },
    {
        "lang": "pl", "seed": "domowe przetwory i fermentacja", "problem": "Niepewność czy przetwory są bezpieczne",
        "persona": ("Grażyna", "działkowiczka", "sprawdzone przepisy krok po kroku"),
        "screens": [
            ("Start", "Wybór warzyw", "Co masz z ogrodu", "Dalej"),
            ("Przepisy", "Przepisy sezonowe", "Przepisy dopasowane do plonów", "Pokaż przepisy"),
            ("Przepis", "Instrukcja krok po kroku", "Kroki z minutnikiem", "Gotuj"),
            ("Spiżarnia", "Spiżarnia", "Daty ważności słoików", "Dodaj do spiżarni"),
        ],
    },
    {
        "lang": "pl", "seed": "aplikacja dla biegaczy amatorów", "problem": "Kontuzje przez zbyt szybkie zwiększanie dystansu",
        "persona": ("Robert", "biegacz amator", "bezpieczny plan na 10 km"),
        "screens": [
            ("Start", "Cel biegowy", "Dystans i termin zawodów", "Ustaw cel"),
            ("Plan", "Plan treningowy", "Bezpieczny przyrost kilometrów", "Pokaż plan"),
            ("Bieg", "Śledzenie biegu", "Tempo i dystans na żywo", "Start biegu"),
            ("Analiza", "Analiza biegu", "Obciążenie i regeneracja", "Zobacz analizę"),
        ],
    },
    {
        "lang": "pl", "seed": "rozliczanie rachunków ze współlokatorami", "problem": "Kłótnie o niespłacone rachunki",
        "persona": ("Daria", "studentka", "uczciwy podział rachunków"),
        "screens": [
            ("Start", "Grupa mieszkania", "Zaproszenie współlokatorów", "Utwórz grupę"),
            ("Rachunek", "Dodanie rachunku", "Kwota i podział", "Dodaj rachunek"),
            ("Saldo", "Saldo grupy", "Kto komu ile winien", "Pokaż saldo"),
            ("Rozliczenie", "Szybkie rozliczenie", "Przelew jednym dotknięciem", "Rozlicz"),
        ],
    },
    {
        "lang": "pl", "seed": "wybór szkoły dla dziecka", "problem": "Rozproszone informacje o szkołach",
        "persona": ("Monika", "mama sześciolatka", "porównanie szkół w okolicy"),
        "screens": [
            ("Start", "Adres zamieszkania", "Szkoły w rejonie", "Szukaj szkół"),
            ("Szkoły", "Lista szkół", "Wyniki i opinie rodziców", "Porównaj"),
            ("Porównanie", "Porównanie szkół", "Tabela kluczowych cech", "Wybierz szkołę"),
            ("Zapis", "Dzień otwarty", "Zapis na dzień otwarty", "Zapisz się"),
        ],
    },
    {
        "lang": "pl", "seed": "aplikacja do nauki tańca", "problem": "Brak odwagi na zajęciach grupowych",
        "persona": ("Weronika", "recepcjonistka", "nauka kroków w domu"),
        "screens": [
            ("Powitanie", "Wybór stylu", "Salsa, bachata, swing", "Wybierz styl"),
            ("Kurs", "Kurs dla początkujących", "Krótkie lekcje wideo", "Rozpocznij kurs"),
            ("Lekcja", "Lekcja w zwolnionym tempie", "Kroki w zwolnionym tempie", "Odtwórz"),
            ("Nagranie", "Porównanie z nagraniem", "Ocena własnego nagrania", "Nagraj się"),
        ],
    },
    {
        "lang": "en", "seed": "habit tracker for students", "problem": "Good intentions fade after a week",
        "persona": ("Liam", "university student", "keeping a study streak"),
        "screens": [
            ("Welcome", "Quick onboarding", "First habit in one minute", "Get started"),
            ("Habits", "Habit templates", "Ready-made study habits", "Pick habit"),
            ("Today", "Daily check-in", "One tap to log a habit", "Check in"),
            ("Streak", "Streak overview", "Streak and weekly chart", "View streak"),
        ],
    },
    {
        "lang": "en", "seed": "parking spot finder", "problem": "Circling the block to find parking",
        "persona": ("Sarah", "sales representative", "a free spot near the client"),
        "screens": [
            ("Map", "Live parking map", "Free spots near destination", "Find parking"),
            ("Spot", "Spot details", "Price and walking time", "Select spot"),
            ("Payment", "One-tap payment", "Pay for exact minutes", "Pay"),
            ("Session", "Parking timer", "Reminder before expiry", "Start parking"),
        ],
    },
    {
        "lang": "en", "seed": "recipe app for leftovers", "problem": "Food goes to waste in the fridge",
        "persona": ("Ben", "young professional", "dinner from what is left"),
        "screens": [
            ("Start", "Fridge scan", "Ingredients from a photo", "Scan fridge"),
            ("Ingredients", "Ingredient list", "Edit detected items", "Confirm"),
            ("Recipes", "Matching recipes", "Recipes using leftovers", "Show recipes"),
            ("Cooking", "Step by step mode", "Hands-free cooking steps", "Cook"),
        ],
    },
    {
        "lang": "en", "seed": "freelancer invoicing", "problem": "Late payments from clients",
        "persona": ("Priya", "freelance designer", "sending invoices in minutes"),
        "screens": [
            ("Home", "Client list", "Saved client details", "New invoice"),
            ("Invoice", "Invoice builder", "Items and tax filled in", "Add item"),
            ("Preview", "Invoice preview", "PDF preview before sending", "Preview"),
            ("Sent", "Payment tracking", "Reminders for late payers", "Send invoice"),
        ],
    },
    {
        "lang": "en", "seed": "language exchange meetups", "problem": "No one to practise speaking with",
        "persona": ("Diego", "expat engineer", "weekly conversation partner"),
        "screens": [
            ("Welcome", "Language profile", "Native and target language", "Continue"),
            ("Partners", "Partner matching", "Partners nearby", "Browse partners"),
            ("Profile", "Partner profile", "Interests and schedule", "Say hello"),
            ("Meetup", "Meetup booking", "Cafe and time", "Book meetup"),
        ],
    },
    {
        "lang": "en", "seed": "elderly medication reminders", "problem": "Missed doses of daily medicine",
        "persona": ("Margaret", "retired teacher", "never missing a pill"),
        "screens": [
            ("Start", "Large text mode", "Readable without glasses", "Begin"),
            ("Medicines", "Medicine list", "Pills with photos", "Add medicine"),
            ("Schedule", "Dose schedule", "Times for each pill", "Set times"),
            ("Today", "Today's doses", "Confirm taken doses", "Mark taken"),
        ],
    },
]

TEST_SEEDS = {
    "rezerwacja wizyt u fryzjera",
    "kontrola cukrzycy",
    "wolontariat w okolicy",
    "aplikacja dla biegaczy amatorów",
    "wybór szkoły dla dziecka",
    "freelancer invoicing",
}

EXTRAS = {
    "pl": [
        ("Pomoc", "link", 1), ("Ustawienia", "link", 1), ("Szukaj", "input", 1), ("Filtry", "select", 6),
        ("Kategorie", "list", 9), ("Powiadomienia", "toggle", 1), ("Sortuj", "select", 4), ("Udostępnij", "button", 1),
        ("Polecane", "list", 8), ("Tryb ciemny", "toggle", 1), ("Ulubione", "link", 1), ("Profil", "link", 1),
        ("Historia", "list", 10), ("Język", "select", 5), ("Regulamin", "link", 1), ("Oceń aplikację", "link", 1),
        ("Tagi", "list", 12), ("Zaproś znajomych", "button", 1), ("Notatki", "input", 1), ("Pokaż więcej", "link", 1),
    ],
    "en": [
        ("Help", "link", 1), ("Settings", "link", 1), ("Search", "input", 1), ("Filters", "select", 6),
        ("Categories", "list", 9), ("Notifications", "toggle", 1), ("Sort", "select", 4), ("Share", "button", 1),
        ("Featured", "list", 8), ("Dark mode", "toggle", 1), ("Favorites", "link", 1), ("Profile", "link", 1),
        ("History", "list", 10), ("Language", "select", 5), ("Terms", "link", 1), ("Rate app", "link", 1),
        ("Tags", "list", 12), ("Invite friends", "button", 1), ("Notes", "input", 1), ("Show more", "link", 1),
    ],
}

NEXT_LABEL = {"pl": ["Dalej", "Przejdź dalej", "Kontynuuj"], "en": ["Next", "Continue", "Go on"]}
SKIP_LABEL = {"pl": "Pomiń", "en": "Skip"}
