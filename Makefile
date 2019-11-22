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
	python -m pip install --upgrade pip
	pip install -r requirements.txt

download_test_assets:
	mkdir test/
	mkdir test/db
	touch test/db/library_test.db
	bash scripts/download_benchmark.sh
