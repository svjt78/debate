import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',timeout:30000,use:{baseURL:process.env.PLAYWRIGHT_BASE_URL||'http://127.0.0.1:8787',launchOptions:{executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'},viewport:{width:1440,height:1000}},reporter:[['list']],outputDir:'test-results'});
