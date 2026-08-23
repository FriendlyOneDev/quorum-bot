-- weekly_posts.chat_id was BIGINT, but channels can be @username strings
-- (Main is @Mage8Elements), not just numeric supergroup IDs. Widen to TEXT.
ALTER TABLE weekly_posts ALTER COLUMN chat_id TYPE TEXT USING chat_id::text;
