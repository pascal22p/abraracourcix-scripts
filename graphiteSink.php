<?php
error_reporting(E_ALL);

$data = trim(file_get_contents('php://input')).PHP_EOL;

try {
    $fp = fsockopen("tcp://127.0.0.1", 2003, $errno, $errstr);

    if (!empty($errno)) echo $errno;
    if (!empty($errstr)) echo $errstr;

    $bytes = fwrite($fp, $data);
    if($bytes == strlen($data)) {
      echo $data;
      http_response_code(202);
    } else {
      echo "Size does not match";
      http_response_code(500);
    }
} catch (Exception $e) {
    echo "\nNetwork error: ".$e->getMessage();
    http_response_code(500);
}


?>
