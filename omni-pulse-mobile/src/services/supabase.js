import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL || "https://dummyproject.supabase.co";
const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || "dummy-key";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY); 