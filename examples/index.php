<?php

namespace App;

use App\Models\User;
use App\Services\AuthService;

require_once 'bootstrap.php';

class Controller {
    public function index() {
        $auth = new AuthService();
        return $auth->getUser();
    }
}

function helperFunction() {
    return "Hello world";
}
