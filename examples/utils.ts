import { useState, useEffect } from 'react';
import axios from 'axios';
import { Config } from './config';

export interface User {
    id: string;
    username: string;
}

export class UserClient {
    private baseUrl: string;

    constructor(baseUrl: string) {
        self.baseUrl = baseUrl;
    }

    async getUser(id: string): Promise<User> {
        const res = await axios.get(`${self.baseUrl}/users/${id}`);
        return res.data;
    }
}

export const fetchConfig = () => {
    return axios.get('/config');
};
