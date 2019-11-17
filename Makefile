clean:
	rm -rf test

isort:
	sh -c "isort --skip-glob=.tox --recursive . "

lint:
	flake8 --exclude=.tox

test: clean download_test_assets
	python test_corpus_analysis.py

test_without_download:
	python test_corpus_analysis.py

setup_env:
	virtualenv ~/readability-metric

setup_mongo:
	sudo service mongod start
	rm /var/lib/mongodb/mongod.lock

run: source
	python /home/rcl/readability-measure/corpus_analysis.py /media/root/terabyte

source:
	. bin/activate

install:
	sudo apt install mongodb
	sudo apt install default-libmysqlclient-dev
	python -m pip install --upgrade pip
	pip install -r requirements.txt

download_test_assets:
	mkdir test/
	mkdir test/db
	touch test/db/library_test.db
	mkdir test/books
	wget https://www.gutenberg.org/ebooks/24264.epub.noimages?session_id=13a48cb17a2a788bd0df32eb9d11b2cc90e5ffb6 -O test/books/hongloumeng.epub
	wget https://www.gutenberg.org/ebooks/6099.epub.noimages?session_id=e525c6c0f4f2faf96f365aabedf179ef08f4f236 -O test/books/lesfleursdumal.epub
	wget https://www.gutenberg.org/ebooks/21000.epub.noimages?session_id=e525c6c0f4f2faf96f365aabedf179ef08f4f236 -O test/books/faust.epub
	wget https://www.gutenberg.org/ebooks/23306.epub.noimages?session_id=13a48cb17a2a788bd0df32eb9d11b2cc90e5ffb6 -O test/books/meditationes.epub
	wget https://www.gutenberg.org/ebooks/2000.epub.noimages?session_id=13a48cb17a2a788bd0df32eb9d11b2cc90e5ffb6 -O test/books/Quijote.epub
	wget https://www.gutenberg.org/ebooks/521.epub.noimages?session_id=13a48cb17a2a788bd0df32eb9d11b2cc90e5ffb6 -O test/books/crusoe.epub
	wget https://www.gutenberg.org/ebooks/2701.epub.noimages?session_id=37b8b8ef79424fa1e6b7a18eb4b341d5de076f03 -O test/books/moby.epub
	wget https://www.gutenberg.org/ebooks/500.epub.noimages?session_id=37b8b8ef79424fa1e6b7a18eb4b341d5de076f03 -O test/books/pinocchio.epub
