for i in {1..11000}
do
    wget -O $1$i.epub bibliothequenumerique.tv5monde.com/download/epub/$i
    find ${1} -name "*.epub" -size -88k -delete
done
