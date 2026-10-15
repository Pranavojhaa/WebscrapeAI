import json

def export_table(table_df, file_format='csv'):
    if file_format == 'csv':
        table_df.to_csv("exported_table.csv", index=False)
    elif file_format == 'json':
        table_df.to_json("exported_table.json", orient='records')
    elif file_format == 'excel':
        table_df.to_excel("exported_table.xlsx", index=False)
    print("✅ Table export successful!")

def export_text_data(data_list, file_format='txt', filename='exported_text'):
    if file_format == 'txt':
        with open(f"{filename}.txt", 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(data_list))
    elif file_format == 'json':
        with open(f"{filename}.json", 'w', encoding='utf-8') as f:
            json.dump(data_list, f, indent=4)
    print(f"✅ {filename.capitalize()} export successful!")

def export_links(links_list):
    with open("exported_links.json", 'w', encoding='utf-8') as f:
        json.dump(links_list, f, indent=4)
    print("✅ Links export successful!")

def export_images(images_list):
    with open("exported_images.txt", 'w', encoding='utf-8') as f:
        f.write('\n'.join(images_list))
    print("✅ Images export successful!")
