Your photo library (made by Photo Lifeboat)

Open index.html in any web browser. It needs no internet and no Google account.

What is here
  Library/YYYY/MM/   every photo and video, filed by the date Google had stored for it (UTC).
  Library/Undated/   files where no trustworthy date was found. They are listed in UNKNOWN.csv.
  Albums/<name>/     one page per album (index.html). Albums point at the single copy in Library/, so photos are not stored twice.
  index.html         album viewer: browse by album or year, with captions and dates.
  manifest.csv       every file with its SHA-256 fingerprint, date, source ZIP, albums and caption.
  UNKNOWN.csv        every file with no matching details file, no usable date, or that could not be read.

About dates
  Dates are in UTC (Google does not store the time zone). For JPEG files that had no capture date inside them,
  the date was added to the file (DateTimeOriginal, with offset +00:00). All other files are byte-for-byte as Google exported them;
  their date is only in manifest.csv and the viewer. No date is ever guessed.

This run: 2 ZIP file(s), 28 photos/videos found, 26 files written, 2 repeat copies merged, 20 dates added inside JPEGs, 2 albums, 7 items in UNKNOWN.csv, 0 errors.

Photo Lifeboat only reads what Google exported. It cannot recover photos that were never in your download.
