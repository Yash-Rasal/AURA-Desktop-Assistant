import Database from "@tauri-apps/plugin-sql";

let db = null;

export async function getDatabase() {
  if (!db) {
    try {
      db = await Database.load("sqlite:aura.db");
      console.log("Database loaded Sucessfully");
    }catch(err){
      console.log("Database loading failed.");
      throw err;
    }
  }

  return db;
}

