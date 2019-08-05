canon="/home/rcl/readability-measure/canon/chinese.txt"
analized="/home/rcl/readability-measure/tagging/zh-TW.tsv"
list=""
while read -r author_canon title_canon; do
        list+=$author_canon
        list+=" "
done < "$canon"
unique_authors=$(tr ' ' '\n' <<< $list | sort -u)
echo $unique_authors
while read -r filesize lexicalVariety intercept slope language author_list title_list type subject source rights relation publisher identifier format contibutor date; do
    flag=0
    while read -r author_canon title_canon; do
        if [ "$author_list" == "$author_canon" ] && [ "$title_list" == "$title_canon" ]; then
            #printf '%s %s Canon match!!\n' "$author_list" "$title_list"
            flag=1
        fi
    done < "$canon"
    for word in $unique_authors; do
        if [ "$author_list" == "$word" ] && [ "$flag" != 1 ]; then
            #printf '%s %s Extended canon match!!\n' "$author_list" "$title_list"
        fi
    done
done < "$analized"
