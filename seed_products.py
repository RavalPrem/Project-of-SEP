import sqlite3
import json


def seed_products():
    # connect to the same database used by the app
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # if there are already products, don't insert duplicates
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]
    if count > 0:
        print(f"Products table already has {count} rows. No new products inserted.")
        conn.close()
        return

    # load products from both JSON files
    all_items = []
    for filename in ("product1.json", "product2.json"):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                all_items.extend(json.load(f))
        except FileNotFoundError:
            print(f"Warning: {filename} not found, skipping.")

    for item in all_items:
        name = item.get("mobile_device_model")
        price = item.get("price_inr")
        description = item.get("description")
        image = item.get("image")

        cursor.execute(
            "INSERT INTO products(name, price, description, image) VALUES (?, ?, ?, ?)",
            (name, price, description, image),
        )

    conn.commit()
    conn.close()
    print(f"Inserted {len(all_items)} products into the database.")


if __name__ == "__main__":
    seed_products()


