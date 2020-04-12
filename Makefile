clean:
	rm -rf test

isort:
	sh -c "isort --skip-glob=.tox --recursive . "

lint:
	flake8 --exclude=.tox

test: clean
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
	sudo rm /etc/apt/sources.list.d/mongodb*.list
	sudo bash -c 'echo "deb http://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/4.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-4.0.list'
	sudo apt update
	sudo apt install mongodb-org
	python -m pip install --upgrade pip
	pip install -r requirements.txt

download_test_assets:
	mkdir test/
	mkdir test/db
	touch test/db/library_test.db
	bash scripts/download_benchmark.sh
