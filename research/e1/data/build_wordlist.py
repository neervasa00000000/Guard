#!/usr/bin/env python3
"""Build the 20,000-word list. Not called by make all.

wordfreq 3.1.1: top_n_list('en', 60000), keep isalpha and isascii, take the first 20,000.
The prior is word_frequency(word, 'en').
"""
import csv
import sys
from pathlib import Path


def main():
    try:
        from wordfreq import top_n_list, word_frequency
    except ImportError:
        print("wordfreq==3.1.1 is not installed", file=sys.stderr)
        return 1
    words = [word for word in top_n_list("en", 60000) if word.isalpha() and word.isascii()][:20000]
    dest = Path(__file__).resolve().parent / "words_20000.csv"
    with dest.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["word", "frequency"])
        for word in words:
            writer.writerow([word, word_frequency(word, "en")])
    print(f"Wrote {len(words)} words to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
