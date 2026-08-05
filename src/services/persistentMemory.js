import { getDatabase } from "./database";

const SINGLETON_CATEGORIES = new Set(["name", "location", "profession"]);

const CATEGORY_LABELS = {
  name: "Name",
  location: "Location",
  profession: "Profession",
  preference: "Preference",
  hobby: "Hobby",
  project: "Project",
  goal: "Goal",
  deadline: "Deadline",
};

export async function saveFact(category, fact) {
  const db = await getDatabase();
  const normalizedFact = fact.trim();

  if (!normalizedFact) {
    return;
  }

  if (SINGLETON_CATEGORIES.has(category)) {
    await db.execute("DELETE FROM user_facts WHERE category = ?", [category]);
  } else {
    const existing = await db.select(
      "SELECT id FROM user_facts WHERE category = ? AND LOWER(fact) = LOWER(?)",
      [category, normalizedFact],
    );

    if (existing.length > 0) {
      return;
    }
  }

  await db.execute(
    "INSERT INTO user_facts (category, fact) VALUES (?, ?)",
    [category, normalizedFact],
  );
}

export async function saveFacts(facts) {
  const db = await getDatabase();
  try {
    await db.execute("BEGIN TRANSACTION;");
    for (const { category, fact } of facts) {
      await saveFact(category, fact);
    }
    await db.execute("COMMIT;");
  } catch (error) {
    console.error("Database transaction failed, rolling back:", error);
    try {
      await db.execute("ROLLBACK;");
    } catch (rollbackError) {
      console.error("Rollback failed:", rollbackError);
    }
    throw error;
  }
}

export async function loadUserFacts() {
  try {
    const db = await getDatabase();

    const rows = await db.select(
      "SELECT category, fact FROM user_facts ORDER BY category ASC, updated_at DESC",
    );

    return rows || [];
  } catch (error) {
    console.warn("Could not load user facts from database:", error);
    return [];
  }
}

export function formatFactsForPrompt(facts) {
  if (facts.length === 0) {
    return "No stored facts yet.";
  }

  return facts
    .map(({ category, fact }) => {
      const label = CATEGORY_LABELS[category] ?? category;
      return `- ${label}: ${fact}`;
    })
    .join("\n");
}
